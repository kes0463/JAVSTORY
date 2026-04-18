"""Harvest DB + canonical(library_state.json) 요약 — GUI용 얇은 브리지."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from javstory.library.cover_cache import cover_needs_download, resolve_cover_path
from javstory.library.paths import library_state_path, work_library_dir


@dataclass
class LibraryWorkSummary:
    product_code: str
    title_ko: str
    title_ja: str
    actors_ko: str
    maker_ko: str
    release_date: str
    synopsis_ko: str
    genres_ko: str
    cover_local_path: str | None
    cover_image_url: str | None
    has_canonical: bool
    scene_count: int
    still_total: int
    overall_summary_preview: str
    # --- 확장: 파이프라인·표지·정렬 ---
    has_harvest: bool
    has_transcription: bool
    has_translation: bool
    is_hardcoded: bool
    has_ja_srt: bool
    has_ko_srt: bool
    lamp_hardcoded: bool
    pipeline_stage: Literal["none", "harvest", "transcription", "translation", "canonical"]
    cover_effective_path: str | None
    cover_needs_download_flag: bool
    updated_at_iso: str
    folder_path: str | None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def canonical_quick_stats(product_code: str) -> tuple[bool, int, int, str]:
    """(library_state 존재, 씬 수, 스틸 합계, overall_summary 앞부분)"""
    p = library_state_path(product_code)
    if not p.is_file():
        return False, 0, 0, ""
    d = _read_json(p)
    scenes = d.get("scenes") if isinstance(d.get("scenes"), list) else []
    n_stills = 0
    for s in scenes:
        if isinstance(s, dict):
            sp = s.get("still_paths")
            if isinstance(sp, list):
                n_stills += len(sp)
    summary = (d.get("overall_summary") or "").strip().replace("\n", " ")
    prev = summary[:200] + ("…" if len(summary) > 200 else "")
    return True, len(scenes), n_stills, prev


def _first_video_in_dir(d: Path, depth=0) -> Path | None:
    if not d.is_dir():
        return None
    from javstory.library.video_ext import is_video_file

    # 1단계: 직하위 파일 우선 탐색
    files = sorted(list(d.iterdir()))
    for p in files:
        if p.is_file() and is_video_file(p):
            return p
    
    # 2단계: 하위 폴더 재귀 탐색 (최대 깊이 2단계)
    if depth < 2:
        for p in files:
            if p.is_dir():
                res = _first_video_in_dir(p, depth + 1)
                if res:
                    return res
    return None


SELF_SUBTITLE_MARKER = "자체자막"


# 파일·폴더명에 이 문자열만 있을 때 자체자막 램프 (일반 `[자막]` 태그는 제외)
_SELF_SUBTITLE_NAME_RE = re.compile(r"자체\s*자막")


def path_contains_self_subtitle_marker(video_path: Path | None, folder_path: str | None, product_code: str = "") -> bool:
    """폴더·파일 이름에「자체자막」「자체 자막」연속 문자열만 허용. `[자막]` 단독 등은 제외."""

    target_texts = []
    if video_path:
        target_texts.append(video_path.name)
        target_texts.extend(video_path.parts)

    fp = (folder_path or "").strip()
    if fp:
        try:
            p_fp = Path(fp)
            target_texts.append(p_fp.name)
            target_texts.extend(p_fp.parts)
        except Exception:
            pass

    for text in target_texts:
        if _SELF_SUBTITLE_NAME_RE.search(text):
            if product_code:
                print(f"[Debug] 자체자막 감지 필터 작동! ({product_code})")
                print(f"  - 걸린 텍스트: '{text}'")
            return True
    return False


def _sidecar_srt_flags(video_path: Path) -> tuple[bool, bool, bool]:
    stem = str(video_path.with_suffix(""))
    ja = Path(stem + ".ja.srt").is_file()
    ko = Path(stem + ".ko.srt").is_file()
    plain = Path(stem + ".srt").is_file()
    return ja, ko, plain


def file_rule_lamp_stt_sub(ja: bool, ko: bool, plain: bool) -> tuple[bool, bool]:
    """
    영상과 같은 stem의 `.ja.srt` / `.ko.srt` / `.srt` 존재만으로 STT·Subtitle 램프 규칙.
    (ja+ko → 둘 다, ja만 → STT만, ko만 또는 plain만(일반 .srt) → Subtitle만 등)
    """
    if ja and ko:
        return True, True
    if ja:
        return True, False
    if ko:
        return False, True
    if plain:
        return False, True
    return False, False


def _scan_data_media_srt_flags(product_code: str) -> tuple[bool, bool, bool]:
    """
    `data/media/<품번>/` 아래 트리에 자막 파일이 있는지.
    영상 파일을 찾지 못했거나 사이드카와 무관한 위치에 산출물만 있을 때 카드 램프 보강용.
    """
    from javstory.config.app_config import MEDIA_ROOT

    pc = (product_code or "").strip().upper()
    if not pc:
        return False, False, False
    root = MEDIA_ROOT / pc
    if not root.is_dir():
        return False, False, False
    has_ja = has_ko = has_plain = False
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            n = p.name.lower()
            if n.endswith(".ja.srt"):
                has_ja = True
            elif n.endswith(".ko.srt"):
                has_ko = True
            elif n.endswith(".srt"):
                has_plain = True
            if has_ja and has_ko and has_plain:
                break
    except OSError:
        pass
    return has_ja, has_ko, has_plain


def _merge_lamp_with_media_artifacts(
    fstt: bool,
    fsub: bool,
    effective_hardcoded: bool,
    product_code: str,
) -> tuple[bool, bool, bool]:
    mj, mk, mpl = _scan_data_media_srt_flags(product_code)
    m_stt, m_sub = file_rule_lamp_stt_sub(mj, mk, mpl)
    return (bool(fstt or m_stt), bool(fsub or m_sub), effective_hardcoded)


def compute_library_lamp_flags(
    *,
    product_code: str,
    video_path: Path | None,
    folder_path: str | None,
    db_is_hardcoded: bool,
) -> tuple[bool, bool, bool]:
    """
    라이브러리 그리드/상세의 STT·Subtitle·자체자막 램프 (done/pending).
    파일명/폴더명에 '자체자막' 마커가 없으면 DB 값이 True여도 False로 강제 필터링함.
    """
    pc = (product_code or "").strip().upper()
    vp = video_path
    
    # 1. 파일명 기반 자체자막 마커 확인 (가장 확실한 증거)
    has_path_marker = path_contains_self_subtitle_marker(vp, folder_path, pc)
    
    # [핵심] 사용자의 요청: 이름에 없으면 DB에 있어도 표시하지 마라.
    effective_hardcoded = False
    if has_path_marker:
        effective_hardcoded = True
    elif bool(db_is_hardcoded):
        # DB에만 있고 이름에는 없는 경우 -> 표시하지 않음 (오탐 방지)
        effective_hardcoded = False

    # 폴더·파일명에 자체자막 마커가 있으면 외부 자막 작품으로 보고 STT/번역 램프는 끈다.
    if has_path_marker:
        return False, False, True

    from javstory.pipeline.orchestrator import get_pipeline_status

    # 2. 폴더 미연결 상태 (기본 수집 정보 기반)
    if vp is None or not vp.is_file():
        st = get_pipeline_status(product_code=pc, video_path=None)
        return _merge_lamp_with_media_artifacts(
            bool(st.ja_srt_exists),
            bool(st.ko_srt_exists or st.srt_fallback_exists),
            effective_hardcoded,
            pc,
        )

    # 3. 폴더 연결 상태
    st = get_pipeline_status(product_code=pc, video_path=vp)
    ja, ko, pl = _sidecar_srt_flags(vp)
    
    # 별도 자막 파일이 없는 경우 상위 단계(STT/Sub)는 앱 산출물 캐시 활용
    if not ja and not ko and not pl:
        return _merge_lamp_with_media_artifacts(
            bool(st.ja_srt_exists),
            bool(st.ko_srt_exists or st.srt_fallback_exists),
            effective_hardcoded,
            pc,
        )

    # 4. 별도 자막 파일 시스템 규칙 적용
    fstt, fsub = file_rule_lamp_stt_sub(ja, ko, pl)
    return _merge_lamp_with_media_artifacts(fstt, fsub, effective_hardcoded, pc)


def guess_video_path_for_product(product_code: str, folder_path: str | None = None) -> Path | None:
    """작품 폴더(DB 저장 경로, 라이브러리, MEDIA_ROOT) 직하위에서 첫 동영상 탐색."""
    pc = (product_code or "").strip().upper()
    if not pc:
        return None
    from javstory.config.app_config import MEDIA_ROOT

    search_dirs = []
    if folder_path and Path(folder_path).is_dir():
        search_dirs.append(Path(folder_path))
    
    search_dirs.extend([work_library_dir(pc), MEDIA_ROOT / pc])

    for base in search_dirs:
        v = _first_video_in_dir(base)
        if v is not None:
            return v
    return None


def _pipeline_stage(
    *,
    has_harvest: bool,
    has_transcription: bool,
    has_translation: bool,
    has_canonical: bool,
) -> Literal["none", "harvest", "transcription", "translation", "canonical"]:
    if has_canonical:
        return "canonical"
    if has_translation:
        return "translation"
    if has_transcription:
        return "transcription"
    if has_harvest:
        return "harvest"
    return "none"


def _row_updated_at_iso(row: Any) -> str:
    u = getattr(row, "updated_at", None)
    if isinstance(u, datetime):
        return u.replace(microsecond=0).isoformat()
    return ""


def row_to_summary(row: Any) -> LibraryWorkSummary:
    """SQLAlchemy JAVMetadata 행 → LibraryWorkSummary."""
    pc = (getattr(row, "product_code", None) or "").strip()
    has_c, n_sc, n_st, prev = canonical_quick_stats(pc)

    title_ko = (getattr(row, "title_ko", None) or getattr(row, "title", None) or "").strip()
    title_ja = (getattr(row, "title_ja", None) or getattr(row, "original_title", None) or "").strip()
    has_harvest = bool(title_ko or title_ja)

    cover_local = getattr(row, "cover_image_local_path", None)
    cover_url = getattr(row, "cover_image_url", None)
    folder_path_raw = getattr(row, "folder_path", None)
    folder_path = (folder_path_raw or "").strip() or None

    has_transcription = False
    has_translation = False
    has_ja_srt = False
    has_ko_srt = False
    lamp_hardcoded = False

    vp = guess_video_path_for_product(pc, folder_path)
    db_hardcoded = bool(getattr(row, "is_hardcoded", False))
    try:
        lamp_stt, lamp_sub, lamp_hardcoded = compute_library_lamp_flags(
            product_code=pc,
            video_path=vp,
            folder_path=folder_path,
            db_is_hardcoded=db_hardcoded,
        )
        has_ja_srt = lamp_stt
        has_ko_srt = lamp_sub
        has_transcription = lamp_stt
        has_translation = lamp_sub
    except Exception:
        has_transcription = False
        has_translation = False
        has_ja_srt = False
        has_ko_srt = False
        lamp_hardcoded = db_hardcoded

    stage = _pipeline_stage(
        has_harvest=has_harvest,
        has_transcription=has_transcription,
        has_translation=has_translation,
        has_canonical=has_c,
    )

    eff = resolve_cover_path(pc, cover_local)
    eff_s = str(eff) if eff else None
    need_dl = cover_needs_download(pc, cover_url, cover_local)

    return LibraryWorkSummary(
        product_code=pc,
        title_ko=title_ko,
        title_ja=title_ja,
        actors_ko=(getattr(row, "actors_ko", None) or getattr(row, "actors", None) or "").strip(),
        maker_ko=(getattr(row, "maker_ko", None) or getattr(row, "maker", None) or "").strip(),
        release_date=(getattr(row, "release_date", None) or "").strip(),
        synopsis_ko=(getattr(row, "synopsis_ko", None) or getattr(row, "synopsis", None) or "").strip(),
        genres_ko=(getattr(row, "genres_ko", None) or getattr(row, "genres", None) or "").strip(),
        cover_local_path=cover_local,
        cover_image_url=cover_url,
        has_canonical=has_c,
        scene_count=n_sc,
        still_total=n_st,
        overall_summary_preview=prev,
        has_harvest=has_harvest,
        has_transcription=has_transcription,
        has_translation=has_translation,
        is_hardcoded=bool(getattr(row, "is_hardcoded", False)),
        has_ja_srt=has_ja_srt,
        has_ko_srt=has_ko_srt,
        lamp_hardcoded=lamp_hardcoded,
        pipeline_stage=stage,
        cover_effective_path=eff_s,
        cover_needs_download_flag=need_dl,
        updated_at_iso=_row_updated_at_iso(row),
        folder_path=folder_path,
    )


def load_library_summaries_from_session(session, *, limit: int = 800) -> list[LibraryWorkSummary]:
    """최근 갱신 순 메타 목록 + canonical 요약."""
    from javstory.harvest.database import JAVMetadata

    rows = (
        session.query(JAVMetadata)
        .order_by(JAVMetadata.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [row_to_summary(r) for r in rows]


SortKey = Literal["updated", "product_code", "release_date", "scene_count"]


def sort_summaries(
    items: list[LibraryWorkSummary],
    key: SortKey = "updated",
    *,
    reverse: bool = True,
) -> list[LibraryWorkSummary]:
    """정렬된 새 리스트 반환."""
    out = list(items)

    def sort_key(s: LibraryWorkSummary) -> Any:
        if key == "updated":
            return s.updated_at_iso or ""
        if key == "product_code":
            return s.product_code.upper()
        if key == "release_date":
            return s.release_date or ""
        if key == "scene_count":
            return s.scene_count
        return ""

    out.sort(key=sort_key, reverse=reverse)
    return out


CanonicalFilter = Literal["all", "has_canonical", "no_canonical"]


def filter_summaries(
    items: list[LibraryWorkSummary],
    *,
    canonical_filter: CanonicalFilter = "all",
    text_query: str = "",
) -> list[LibraryWorkSummary]:
    q = (text_query or "").strip().lower()
    out: list[LibraryWorkSummary] = []
    for s in items:
        if canonical_filter == "has_canonical" and not s.has_canonical:
            continue
        if canonical_filter == "no_canonical" and s.has_canonical:
            continue
        if q:
            blob = f"{s.product_code} {s.title_ko} {s.actors_ko}".lower()
            if q not in blob:
                continue
        out.append(s)
    return out
