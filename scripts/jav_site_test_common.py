"""
테스트 스크립트용: 브라우저형 GET, og:image 추출, 상대 URL 절대화.
프로젝트 루트에서 실행: python scripts/test_javdb_crawl.py ABW-138
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.hybrid_crawler import torrent_slug_for_index_sites  # noqa: E402


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }


def _requests_session() -> requests.Session:
    return requests.Session()


def resolve_proxy(cli_proxy: str | None) -> str | None:
    """--proxy 인자가 있으면 우선, 없으면 HTTPS_PROXY / ALL_PROXY 등."""
    s = (cli_proxy or "").strip()
    if s:
        return s
    for key in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        v = (os.getenv(key) or "").strip()
        if v:
            return v
    return None


def _proxies_dict(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def _cloudscraper_session_or_none() -> Any | None:
    try:
        import cloudscraper

        return cloudscraper.create_scraper()
    except Exception:
        return None


def _session_list(*, cloudscraper_first: bool) -> list[tuple[str, Any]]:
    """(라벨, 세션) 순서대로 시도. cloudscraper 미설치 시 requests 만."""
    cs = _cloudscraper_session_or_none()
    rq = _requests_session()
    if cloudscraper_first:
        if cs:
            return [("cloudscraper", cs), ("requests", rq)]
        return [("requests", rq)]
    if cs:
        return [("requests", rq), ("cloudscraper", cs)]
    return [("requests", rq)]


def _curl_cffi_available() -> bool:
    try:
        import curl_cffi  # noqa: F401

        return True
    except ImportError:
        return False


def _try_fetch_curl_cffi(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[int, int],
    proxies: dict[str, str] | None,
) -> tuple[str, str | None, int | None, str | None, str | None]:
    """
    Returns:
        ("ok", _, status, final_url, html) | ("err", message, _, _, _) | ("skip", reason, _, _, _)
    """
    try:
        from curl_cffi import requests as cf_req
    except ImportError:
        return ("skip", "curl-cffi 미설치", None, None, None)

    impersonate = (
        os.getenv("JAVSTORY_SITE_TEST_IMPERSONATE", "chrome120") or "chrome120"
    ).strip()
    connect_t, read_t = timeout
    try:
        r = cf_req.get(
            url,
            headers=headers,
            timeout=read_t,
            allow_redirects=True,
            impersonate=impersonate,
            proxies=proxies,
        )
    except Exception as e:
        return ("err", str(e), None, None, None)

    final = str(r.url)
    enc = getattr(r, "encoding", None) or "utf-8"
    text = r.content.decode(enc, errors="replace")
    return ("ok", impersonate, r.status_code, final, text)


def fetch_html(
    url: str,
    *,
    timeout: tuple[int, int] = (15, 45),
    use_cloudscraper: bool = False,
    proxy: str | None = None,
) -> tuple[int, str, str | None, str | None]:
    """
    Returns:
        (status_code, final_url, html_text_or_none, error_message_or_none)

    - 기본: requests → cloudscraper → **curl_cffi**(Chrome TLS 위장, 패키지 있을 때).
    - use_cloudscraper=True: cloudscraper → requests → curl_cffi.
    - proxy: 명시 URL 또는 resolve_proxy() 결과. 미지정이어도 requests 는 trust_env 로 시스템 프록시를 씀.
    """
    headers = browser_headers()
    proxies = _proxies_dict((proxy or "").strip() or None)
    chain = _session_list(cloudscraper_first=use_cloudscraper)
    errors: list[str] = []
    verbose = parse_bool_env("JAVSTORY_SITE_TEST_VERBOSE", False)

    for idx, (label, sess) in enumerate(chain):
        try:
            r = sess.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                proxies=proxies,
            )
            final = str(r.url)
            enc = r.encoding or "utf-8"
            text = r.content.decode(enc, errors="replace")

            retry_http = r.status_code in (403, 503, 429)
            has_more = idx + 1 < len(chain) or _curl_cffi_available()
            if retry_http and has_more:
                errors.append(f"{label}: HTTP {r.status_code}")
                continue

            if verbose:
                print(f"[jav_site_test] OK via {label} HTTP {r.status_code}", file=sys.stderr)

            return r.status_code, final, text, None
        except Exception as e:
            errors.append(f"{label}: {e!s}")
            continue

    kind, extra, st, final, html = _try_fetch_curl_cffi(
        url, headers=headers, timeout=timeout, proxies=proxies
    )
    if kind == "ok" and st is not None and final is not None and html is not None:
        if st in (403, 503, 429):
            errors.append(f"curl_cffi({extra}): HTTP {st}")
        else:
            if verbose:
                print(
                    f"[jav_site_test] OK via curl_cffi impersonate={extra} HTTP {st}",
                    file=sys.stderr,
                )
            return st, final, html, None
    elif kind == "err":
        errors.append(f"curl_cffi: {extra}")
    elif kind == "skip":
        pass

    msg = " -> ".join(errors) if errors else "알 수 없는 오류"
    extra: list[str] = []
    if len(chain) == 1 and not _cloudscraper_session_or_none():
        extra.append("venv에서 `pip install cloudscraper`")
    if not _curl_cffi_available():
        extra.append("`pip install curl-cffi` (Chrome TLS 위장)")
    if extra:
        msg += "\n힌트: " + " · ".join(extra)

    low = msg.lower()
    if "10061" in msg or "unable to connect to proxy" in low or (
        "failed to connect" in low and "127.0.0.1" in msg
    ):
        msg += (
            "\n힌트: **로컬 프록시**에 붙지 못한 상태입니다(해당 포트에 프로그램이 안 떠 있거나 포트가 다름). "
            "Clash/싱박스 설정의 **HTTP/Mixed 포트**를 확인하고, SOCKS 전용이면 "
            "`--proxy socks5://127.0.0.1:포트` 형식을 쓰세요. 프록시 없이 되면 `--proxy` 를 빼고 실행해 보세요."
        )
    elif "10054" in msg:
        msg += (
            "\n힌트: 원격 호스트가 연결을 끊은 경우(10054) — ISP·지역 차단 가능. "
            "VPN 또는 동작 중인 로컬 프록시로 다시 시도하세요."
        )
    else:
        msg += (
            "\n힌트: 위 오류 종류에 따라 프록시 포트·프로그램 실행 여부, 또는 `--proxy` 생략을 검토하세요."
        )
    return -1, url, None, msg


def extract_og_image(html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find(
        "meta", attrs={"name": "og:image"}
    )
    if not tag:
        # content / property 순서 뒤바뀐 경우
        for m in soup.find_all("meta"):
            prop = (m.get("property") or m.get("name") or "").lower()
            if prop == "og:image":
                tag = m
                break
    if not tag:
        return None
    content = (tag.get("content") or "").strip()
    if not content:
        return None
    return urljoin(base_url, content)


def extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def collect_img_srcs(html: str, base_url: str, limit: int = 12) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img", src=True):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        abs_u = urljoin(base_url, src)
        if abs_u in seen:
            continue
        seen.add(abs_u)
        low = abs_u.lower()
        if any(
            x in low
            for x in (".jpg", ".jpeg", ".png", ".webp", "cover", "pics", "thumb", "image")
        ):
            out.append(abs_u)
        if len(out) >= limit:
            break
    return out


def parse_bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def add_standard_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "code",
        nargs="?",
        default="ABW-138",
        help="품번 (예: ABW-138, SNOS-152)",
    )
    p.add_argument(
        "--cloudscraper",
        action="store_true",
        help="cloudscraper를 먼저 시도한 뒤 requests로 폴백 (기본은 requests 먼저)",
    )
    p.add_argument(
        "--proxy",
        default=None,
        help="HTTP/HTTPS 프록시 (예: http://127.0.0.1:7890). 미지정 시 HTTPS_PROXY 등 환경변수도 사용",
    )


def print_fetch_banner(name: str, url: str) -> None:
    print(f"=== {name} ===")
    print(f"URL: {url}")


def print_fetch_result(status: int, final: str, err: str | None) -> None:
    print(f"HTTP: {status}")
    print(f"최종 URL: {final}")
    if err:
        print(f"오류: {err}")


def is_probably_torrent_missing(
    status: int, html: str | None, host: str
) -> bool:
    if status == 404:
        return True
    if not html:
        return False
    low = html.lower()
    if "404" in low and "not found" in low:
        return True
    if "onejav" in host and "torrent not found" in low:
        return True
    return False


__all__ = [
    "ROOT",
    "torrent_slug_for_index_sites",
    "browser_headers",
    "resolve_proxy",
    "fetch_html",
    "extract_og_image",
    "extract_title",
    "collect_img_srcs",
    "parse_bool_env",
    "add_standard_args",
    "print_fetch_banner",
    "print_fetch_result",
    "is_probably_torrent_missing",
]


if __name__ == "__main__":
    print(
        "이 모듈은 직접 실행용이 아닙니다. 예: python test_javdb_crawl.py ABW-138",
        file=sys.stderr,
    )
