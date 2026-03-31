"""
하이브리드 크롤러 (v8.1.1): 9대 핵심 정보 통합 및 GUI 호환성 복구.
- [FIX] ImportError: run_crawler_phase 함수 완전 복구.
- [DATA] 9개 핵심 필드(메이커, 출시일 등) 모두 DB 저장 지원.
- [TAG] 배우/장르 쉼표 구분 태그 자동 정제.
"""
from __future__ import annotations

import json
import os
import re
import time
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from curl_cffi import requests as curl_requests
from DrissionPage import ChromiumPage, ChromiumOptions

from core.app_config import MEDIA_ROOT, WESERV_IMAGE_PROXY
from core.database import get_db_session, upsert_jav_metadata
from core.product_code import extract_product_code_from_path
from core import bypass_manager
from core.njav_playwright import scrape_njavtv_playwright
from core.image_handler import ImageHandler
from core.actress_resolver import ActressResolver

# njavtv.com 정밀 셀렉터 (nth-child 체인 금지 — 라벨·클래스 기반)
NJAV_TITLE_SELECTORS = ("css:h1.text-nord6", "tag:h1")
NJAV_SYNOPSIS_SELECTORS = ("css:div.text-secondary.break-all", "css:div.break-all.text-secondary", "tag:div@class=break-all")
NJAV_COVER_SELECTOR = ".plyr__poster"

# 텍스트 라벨 매칭 목록
LABELS_TO_PROBE = {
    "product_code": "品番:",
    "release_date": "配信開始日:",
    "actors": "女優:",
    "genres": "ジャンル:",
    "maker": "メーカー:"
}

_MAKER_HREF_MARKERS = ("/makers/", "/maker/")
_NJAV_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_PLACEHOLDER_TITLE_LOWER = frozenset(
    {"njavtv.com", "njavtv", "njav", "njav tv", "just a moment...", "attention required"}
)
# Cloudflare / 봇 체크 등 (제목·대기 화면)
_CHALLENGE_TITLE_FRAGMENTS = (
    "just a moment",
    "please wait",
    "checking your browser",
    "cloudflare",
    "attention required",
    "잠시",
    "기다리",
    "verify you are human",
)


def _slug_for_url(product_code: str | None) -> str:
    if not product_code:
        return ""
    return product_code.strip().lower().replace("_", "-")


def _njav_path_is_dm_detail(href: str) -> bool:
    """상세 페이지: /dm숫자/ja/{slug} (예: /dm18/ja/... 또는 /dm31/ja/...)."""
    try:
        parts = [p for p in urlparse(href).path.split("/") if p]
        if len(parts) < 3:
            return False
        return parts[0].lower().startswith("dm") and parts[1] == "ja"
    except Exception:
        return False


def _curl_resolve_njav_http_redirect(entry_url: str) -> str | None:
    """서버 301/302 체인이면 curl로 최종 URL 확보 (JS 전용 리디렉션이면 None)."""
    try:
        r = curl_requests.get(
            entry_url,
            headers={"User-Agent": _NJAV_UA},
            timeout=30,
            impersonate="chrome120",
            allow_redirects=True,
        )
        u = str(r.url).strip()
        if u and "njavtv.com" in u.lower() and _njav_path_is_dm_detail(u):
            return u
    except Exception:
        pass
    return None


def _wait_njav_detail_url(
    page: Any,
    *,
    slug: str,
    max_wait: float,
) -> str:
    """JS 리디렉션으로 /dm*/ja/slug 가 될 때까지 location.href 폴링."""
    deadline = time.time() + max_wait
    slug_l = _slug_for_url(slug)
    while time.time() < deadline:
        href = (_page_location_href(page) or (getattr(page, "url", None) or "").strip() or "")
        if href and _njav_path_is_dm_detail(href):
            if slug_l:
                parts = [p for p in urlparse(href).path.split("/") if p]
                tail = (parts[-1] if parts else "").lower().replace("_", "-")
                if tail == slug_l or tail.replace("-", "") == slug_l.replace("-", ""):
                    return href
            else:
                return href
        time.sleep(0.35)
    return (_page_location_href(page) or (getattr(page, "url", None) or "").strip() or "")


def _title_looks_placeholder(title: str | None) -> bool:
    s = (title or "").strip().lower()
    if len(s) < 4:
        return True
    if s in _PLACEHOLDER_TITLE_LOWER:
        return True
    if "njav" in s and ".com" in s and len(s) < 24:
        return True
    return False


def _norm_product_code(val: str | None) -> str:
    if not val or not isinstance(val, str):
        return ""
    return re.sub(r"\s+", "", val.strip()).upper()


def _extract_njav_head_meta(html: str, base_url: str) -> dict[str, Any]:
    """head `<meta>` 속성만 사용 (meta:nth-child 금지)."""
    out: dict[str, Any] = {}
    if not (html and html.strip()):
        return out
    soup = BeautifulSoup(html, "html.parser")
    head = soup.find("head")
    if not head:
        return out

    def _content(sel: dict[str, str]) -> str | None:
        tag = head.find("meta", attrs=sel)
        if tag and (tag.get("content") or "").strip():
            return (tag.get("content") or "").strip()
        return None

    og_img = _content({"property": "og:image"}) or _content({"name": "og:image"})
    if og_img:
        out["cover_url"] = urljoin(base_url, og_img)

    title = _content({"property": "og:title"}) or _content({"name": "og:title"})
    if title:
        out["title"] = title
    if not out.get("title") and soup.title and soup.title.string:
        out["title"] = soup.title.string.strip()

    desc = (
        _content({"name": "description"})
        or _content({"property": "og:description"})
        or _content({"name": "twitter:description"})
    )
    if desc:
        out["synopsis"] = desc

    actors: list[str] = []
    for m in head.find_all("meta", attrs={"property": "og:video:actor"}):
        c = (m.get("content") or "").strip()
        if c and c not in actors:
            actors.append(c)
    if actors:
        out["actors"] = actors

    rd = _content({"property": "og:video:release_date"})
    if rd:
        out["release_date"] = rd

    return out


def _merge_njav_body_head(body: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """body 우선, 비어 있거나 없는 키만 head로 보충."""
    merged = dict(body)
    if not head:
        return merged

    if not (merged.get("cover_url") or "").strip() and head.get("cover_url"):
        merged["cover_url"] = head["cover_url"]
    if not (merged.get("title") or "").strip() and head.get("title"):
        merged["title"] = head["title"]
    if not (merged.get("synopsis") or "").strip() and head.get("synopsis"):
        merged["synopsis"] = head["synopsis"]

    b_actors = merged.get("actors")
    if isinstance(b_actors, list) and b_actors:
        pass
    elif isinstance(b_actors, str) and b_actors.strip():
        pass
    elif head.get("actors"):
        merged["actors"] = head["actors"]

    _rd = merged.get("release_date")
    _has_rd = isinstance(_rd, str) and bool(_rd.strip())
    if not _has_rd and head.get("release_date"):
        merged["release_date"] = head["release_date"]

    return merged


def _page_location_href(page: Any) -> str | None:
    try:
        u = page.run_js("return location.href")
        if isinstance(u, str) and u.startswith("http"):
            return u.strip()
    except Exception:
        pass
    return None


def _print_scraped_preview(data: dict[str, Any]) -> None:
    """터미널에 긁어 온 메타 요약 출력."""
    print("[Hybrid] --- 수집 결과 ---")
    order = [
        ("final_url", "최종 URL"),
        ("title", "제목"),
        ("product_code", "품번"),
        ("release_date", "출시일"),
        ("maker", "메이커"),
        ("actors", "배우"),
        ("genres", "장르"),
        ("synopsis", "시놉시스"),
        ("cover_url", "표지 URL"),
    ]
    for key, label in order:
        if key == "final_url":
            v = data.get("_final_url") or data.get("final_url")
        else:
            v = data.get(key)
        if v is None or v == "" or v == []:
            print(f"  {label}: (없음)")
            continue
        if isinstance(v, list):
            preview = ", ".join(str(x) for x in v[:12])
            if len(v) > 12:
                preview += f" … 외 {len(v) - 12}명"
            print(f"  {label}: {preview}")
        elif isinstance(v, str) and len(v) > 200 and key == "synopsis":
            print(f"  {label}: {v[:200]}…")
        else:
            print(f"  {label}: {v}")
    print("[Hybrid] ------------------")


def _raw_has_any_content(raw: dict[str, Any]) -> bool:
    if not raw: return False
    # 유효한 데이터가 하나 이상이라도 있으면 수집 진행 (최소 정보 보전 정책)
    for v in raw.values():
        if v and (isinstance(v, (str, list)) and len(v) > 0):
            return True
    print("[Hybrid] 정보 전멸: 수집된 유의미한 데이터가 전혀 없습니다. (사이트 차단 의심)")
    return False


def _scrape_dict_for_db(raw: dict[str, Any], product_code: str) -> dict[str, Any]:
    """일본어 원문 정리 및 누락 항목 플레이스홀더 처리."""
    code = product_code.upper()
    title = (raw.get("title") or "").strip()
    
    # 제목 누락 또는 의미 없는 제목 처리
    if not title or _title_looks_placeholder(title):
        print(f"[Hybrid] 경고: {code} 제목 누락 -> '제목 없음' 처리")
        title = "제목 없음"

    pc = raw.get("product_code")
    if isinstance(pc, list):
        pc = ", ".join(str(x) for x in pc)
    pc = (str(pc).strip() if pc else "") or code

    def _list_or_str(v: Any) -> str:
        if isinstance(v, list):
            return ", ".join(str(x) for x in v if str(x).strip())
        return str(v).strip() if v else ""

    cover_url = (raw.get("cover_url") or "").strip()
    if not cover_url:
        print(f"[Hybrid] 경고: {code} 이미지 누락 -> '이미지 누락' 처리")
        cover_url = "이미지 누락"

    return {
        "title": title,
        "original_title": title,
        "actors": _list_or_str(raw.get("actors")),
        "genres": _list_or_str(raw.get("genres")),
        "maker": _list_or_str(raw.get("maker")),
        "release_date": _list_or_str(raw.get("release_date")),
        "synopsis": (raw.get("synopsis") or "").strip(),
        "cover_url": cover_url,
        "_source": "njavtv_scrape",
        "_final_url": raw.get("_final_url"),
    }


def _sanity_log_njav(data: dict[str, Any], expected_code: str, final_url: str) -> None:
    exp = _norm_product_code(expected_code)
    if not exp:
        return
    raw_pc = data.get("product_code")
    if isinstance(raw_pc, list):
        raw_pc = raw_pc[0] if raw_pc else ""
    parsed = _norm_product_code(str(raw_pc) if raw_pc is not None else "")
    if parsed and parsed != exp:
        print(f"[Hybrid] 경고: 파싱 품번({raw_pc!r})과 요청 품번({expected_code}) 불일치")

    path_last = ""
    try:
        path_last = (urlparse(final_url).path or "").rstrip("/").rsplit("/", 1)[-1]
    except Exception:
        path_last = ""
    if path_last:
        slug_norm = _norm_product_code(path_last)
        if slug_norm and slug_norm.replace("-", "") != exp.replace("-", ""):
            print(f"[Hybrid] 경고: URL 슬러그({path_last!r})와 품번({expected_code}) 불일치 가능")

    cu = (data.get("cover_url") or "").strip()
    if cu and re.search(r"[a-zA-Z]{2,}\s*-\s*\d+", expected_code):
        needle = re.sub(r"\s+", "", expected_code.upper().replace("-", ""))
        cu_compact = re.sub(r"[^\w]", "", cu.upper())
        if needle and needle not in cu_compact:
            print(f"[Hybrid] 참고: 표지 URL에 품번 축약형이 안 보일 수 있음(정상일 수 있음)")


def normalize_image_url_for_cdn(url: str | None) -> str | None:
    if not url or not isinstance(url, str): return None
    u = url.strip().strip("`").strip('"').strip("'")
    if not u: return None
    if u.startswith("//"): u = "https:" + u
    elif not re.match(r"(?i)^https?://", u):
        if re.match(r"(?i)^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}(/|$)", u): u = "https://" + u
        else: return None
    parsed = urlparse(u)
    if not parsed.netloc: return None
    if parsed.scheme.lower() == "http":
        u = urlunparse(("https", parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return u

def _clean_title(title: str, product_code: str) -> str:
    """제목에서 품번과 감싸는 괄호를 정교하게 제거."""
    if not title: return ""
    code = product_code.upper()
    # 1. 품번과 직접적인 대괄호 쌍 제거 (e.g. [STAR-471])
    cleaned = re.sub(rf"\[\s*{code}\s*\]", "", title, flags=re.IGNORECASE)
    # 2. 품번 단독 제거 (e.g. STAR-471 제목)
    cleaned = re.sub(rf"\b{code}\b", "", cleaned, flags=re.IGNORECASE)
    # 3. 불필요한 공백 및 대시 정제
    cleaned = re.sub(r"^\s*[-_]\s*", "", cleaned.strip())
    return cleaned.strip()

# download_cover_hybrid는 ImageHandler로 대체되었습니다.

class HybridJavCrawler:
    def __init__(self) -> None:
        try: bypass_manager.manager.start()
        except: pass

    def get_local_page_data(self, url: str, expected_product_code: str | None = None) -> dict[str, Any]:
        """브라우저에서 직접 추출: body 라벨·시맨틱 셀렉터 우선, head 메타는 빈 필드 보충."""
        print(f"[Hybrid] 요청 URL: {url}")
        co = ChromiumOptions().set_argument('--no-sandbox').headless()
        page = ChromiumPage(co)
        data: dict[str, Any] = {}
        slug = expected_product_code or ""
        try:
            open_url = url
            http_final = _curl_resolve_njav_http_redirect(url)
            if http_final:
                print(f"[Hybrid] HTTP 리디렉션으로 상세 URL 확보: {http_final}")
                open_url = http_final

            page.get(open_url)
            
            # 사이트 차단 여부 정밀 체크
            if any(term in (page.title or "") for term in ["Access Denied", "403 Forbidden", "Attention Required", "Cloudflare"]):
                print(f"[Hybrid] 사이트 접근 차단 감지: {page.title}")
                return {}

            final_url = _wait_njav_detail_url(page, slug=slug, max_wait=28.0)
            if not final_url or not _njav_path_is_dm_detail(final_url):
                final_url = _wait_njav_detail_url(page, slug=slug, max_wait=8.0)
            href = _page_location_href(page)
            page_attr = (page.url or "").strip()
            final_url = href or final_url or page_attr or open_url
            if href and page_attr and href != page_attr:
                print(f"[Hybrid] 참고: page.url={page_attr!r} → location.href={href!r}")
            if not _njav_path_is_dm_detail(final_url):
                print(
                    f"[Hybrid] 경고: 아직 /dm…/ja/… 상세 경로가 아닙니다 "
                    f"(JS·연령 확인 후 이동 필요할 수 있음). 현재: {final_url!r}"
                )
            print(f"[Hybrid] 최종 URL (location): {final_url}")

            for _ in range(2):
                if ("Just a moment" in page.title or "잠시만 기다려" in page.title) and not page.ele('tag:h1'): time.sleep(5)
                else: break

            age_clicked = False
            for s in ['text:18歳以上', 'text:확인', 'text:Enter', 'text:Yes']:
                btn = page.ele(s, timeout=1)
                if btn:
                    btn.click()
                    age_clicked = True
                    time.sleep(2)
                    break
            if age_clicked:
                final_url = _wait_njav_detail_url(page, slug=slug, max_wait=22.0) or final_url
                href3 = _page_location_href(page)
                if href3:
                    final_url = href3
                if _njav_path_is_dm_detail(final_url):
                    print(f"[Hybrid] 연령 확인 후 상세 URL: {final_url}")
                elif slug:
                    print(f"[Hybrid] 연령 확인 후에도 상세 경로 미도달: {final_url!r} — 계속 파싱 시도")

            for sel in NJAV_TITLE_SELECTORS:
                ele = page.ele(sel, timeout=1)
                if not ele or not (ele.text or "").strip():
                    continue
                t = ele.text.strip()
                if _title_looks_placeholder(t):
                    continue
                data["title"] = t
                break

            for sel in NJAV_SYNOPSIS_SELECTORS:
                ele = page.ele(sel, timeout=1)
                if ele and (ele.text or "").strip():
                    data["synopsis"] = ele.text.strip()
                    break

            poster = page.ele(NJAV_COVER_SELECTOR, timeout=2)
            if poster:
                style = poster.attr('style') or ""
                match = re.search(r'url\(["\']?(.+?)["\']?\)', style)
                if match:
                    data["cover_url"] = match.group(1).replace("&quot;", "").strip('"').strip("'")

            for key, label in LABELS_TO_PROBE.items():
                container = page.ele(f't:div@class=text-secondary?text={label}', timeout=1)
                if not container:
                    continue
                if key == "maker":
                    picked: str | None = None
                    for a in container.eles('tag:a'):
                        href = (a.attr('href') or "")
                        if any(m in href for m in _MAKER_HREF_MARKERS):
                            picked = (a.text or "").strip()
                            if picked:
                                break
                    if picked:
                        data[key] = picked
                    continue

                links = container.eles('tag:a')
                if links:
                    data[key] = [l.text.strip() for l in links if (l.text or "").strip()]
                else:
                    t = container.ele('tag:time')
                    if t:
                        data[key] = t.text.strip()
                    else:
                        data[key] = container.text.replace(label, "").strip()

            href_last = _page_location_href(page)
            if href_last:
                final_url = href_last

            html = page.html or ""
            head_meta = _extract_njav_head_meta(html, final_url)
            data = _merge_njav_body_head(data, head_meta)

            if expected_product_code:
                _sanity_log_njav(data, expected_product_code, final_url)

            data["_final_url"] = final_url
            _print_scraped_preview(data)
            return data
        except Exception as e:
            print(f"[Hybrid] 추출 중 에러: {e}")
            return {}
        finally: page.quit()

    def fetch_metadata_smart(self, product_code: str) -> dict[str, Any]:
        """njavtv Playwright 정밀 크롤러를 이용하여 메타 수집."""
        code = product_code.upper()
        
        # [1] Playwright 기반 크롤 실행
        print(f"[Hybrid] Playwright 기반 njavtv 크롤링 시작: {code}")
        raw = scrape_njavtv_playwright(code)
        
        # [2] 실패 시 기존 DrissionPage 로직을 fallback으로 사용
        if not _raw_has_any_content(raw):
            print("[Hybrid] Playwright 결과 미흡. DrissionPage(Fallback) 시도...")
            njav_url = f"https://njavtv.com/ja/{code.lower()}"
            raw = self.get_local_page_data(njav_url, expected_product_code=code)
            
        if not _raw_has_any_content(raw):
            print("[Hybrid] 모든 시도가 실패했습니다.")
            return {}
            
        # DB 저장용 딕셔너어로 변환
        return _scrape_dict_for_db(raw, code)

def run_crawler_for_video_path(video_path: str | Path, api_key: str | None = None) -> dict[str, Any]:
    video_path = Path(video_path)
    code = extract_product_code_from_path(video_path)
    if not code: return {"ok": False, "message": "품번 추출 실패"}
    res = HybridJavCrawler().fetch_metadata_smart(code)
    if not res: return {"ok": False, "message": "분석 실패"}

    def tagify(val):
        if isinstance(val, (list, tuple)): return ", ".join(map(str, val))
        return str(val) if val else ""

    session = get_db_session()
    try:
        # [1] 데이터 정제 및 배우 이름 변환
        raw_title = tagify(res.get("title"))
        cleaned_title = _clean_title(raw_title, code)
        
        actors_list = res.get("actors", [])
        if isinstance(actors_list, str):
            actors_list = [a.strip() for a in actors_list.split(",") if a.strip()]
        
        resolver = ActressResolver()
        resolved = resolver.resolve_names(actors_list)
        
        # [2] DB Upsert (트랜잭션 시작)
        row = upsert_jav_metadata(
            session, product_code=code, 
            title=cleaned_title,
            original_title=raw_title,
            actors=tagify(resolved["ja"]),
            actors_ja=tagify(resolved["ja"]),
            actors_ko=tagify(resolved["ko"]),
            actors_romaji=tagify(resolved["romaji"]),
            genres=tagify(res.get("genres")), 
            maker=tagify(res.get("maker")),
            release_date=tagify(res.get("release_date")), 
            cover_image_url=res.get("cover_url"), 
            synopsis=tagify(res.get("synopsis"))
        )
        session.commit() # 중간 커밋: 기본 정보 확보

        # [3] 에셋(표지/썸네일) 다운로드 및 로컬 경로 업데이트
        cover_url = res.get("cover_url")
        if cover_url:
            handler = ImageHandler()
            img_results = handler.process_jav_assets(code, cover_url)
            
            if img_results.get("poster_local"):
                row.cover_image_local_path = img_results["poster_local"]
            if img_results.get("thumb_local"):
                row.thumb_image_local_path = img_results["thumb_local"]
            
            session.commit() # 최종 커밋
            print(f"[Hybrid] 에셋 저장 완료: {code}")

        return {"ok": True, "message": f"완료: {code} ({res.get('_source')})", "db_id": row.id}

    except Exception as e:
        session.rollback()
        print(f"[Hybrid] DB 처리 오류: {e}")
        return {"ok": False, "message": f"DB 저장 실패: {e}"}
    finally:
        session.close()

def run_crawler_phase(*args, **kwargs) -> None:
    """기존 파이프라인 스텁과의 호환성을 위한 래퍼 함수 (중요: GUI 구동에 필수)"""
    path = kwargs.get("path") or (args[0] if args else None)
    if not path: return
    res = run_crawler_for_video_path(path)
    if res["ok"]: print(f"[crawler] {res['message']}")
    else: print(f"[crawler] {res['message']}")

if __name__ == "__main__":
    print("--- njavtv 메타 수집 테스트 (STAR-471) ---")
    result = HybridJavCrawler().fetch_metadata_smart("STAR-471")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    try: bypass_manager.manager.stop()
    except Exception: pass
