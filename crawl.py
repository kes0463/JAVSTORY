# njavtv.com 크롤링 - 2026년 3월 기준 안정 버전
"""
CLI / 단독 실행: Playwright로 njavtv 메타 수집 → 콘솔(JSON) + {품번}.json 저장.

headless: 기본 True. 디버깅 시 환경변수 NJAV_HEADLESS=0 또는 scrape_njavtv(..., headless=False).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.njav_playwright import public_payload, scrape_njavtv_playwright

# 디버깅 시 False 로 바꾸거나 환경변수 NJAV_HEADLESS=0
DEFAULT_HEADLESS = True


def _effective_headless(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    v = (os.getenv("NJAV_HEADLESS") or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return DEFAULT_HEADLESS


def _json_filename(code: str) -> str:
    stem = re.sub(r"[^\w\-]+", "_", code.strip().upper()).strip("_") or "UNKNOWN"
    return f"{stem}.json"


def _output_dir() -> Path:
    d = os.getenv("NJAV_JSON_DIR", "").strip()
    if d:
        return Path(d).expanduser().resolve()
    return _ROOT


def scrape_njavtv(
    code: str,
    *,
    headless: bool | None = None,
    save_json: bool = True,
    print_json: bool = True,
) -> dict[str, Any]:
    """
    단일 품번 크롤. 실패해도 예외 대신 dict에 error 키가 들어갈 수 있음.
    """
    code = (code or "").strip()
    if not code:
        err: dict[str, Any] = {"error": "empty code", "code_requested": ""}
        if print_json:
            print(json.dumps(err, ensure_ascii=False, indent=2))
        return err

    hl = _effective_headless(headless)
    try:
        raw = scrape_njavtv_playwright(code, headless=hl, slow_mo=80 if not hl else 0)
    except Exception as e:
        raw = {"code_requested": code, "error": f"playwright: {e}"}

    payload = public_payload(raw)

    if print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if save_json:
        try:
            out_dir = _output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / _json_filename(code)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[crawl] 저장: {path}", file=sys.stderr)
        except Exception as e:
            print(f"[crawl] JSON 저장 실패: {e}", file=sys.stderr)

    return payload


def scrape_multiple(codes: list[str]) -> list[dict[str, Any]]:
    """여러 품번 순차 처리. 각 항목은 독립 dict (일부만 실패해도 계속)."""
    out: list[dict[str, Any]] = []
    for c in codes:
        try:
            item = scrape_njavtv(c.strip(), save_json=True, print_json=True)
            out.append(item)
        except Exception as e:
            row = {"code_requested": (c or "").strip(), "error": str(e)}
            print(json.dumps(row, ensure_ascii=False, indent=2))
            try:
                path = _output_dir() / _json_filename(c or "unknown")
                path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            out.append(row)
    return out


if __name__ == "__main__":
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    if len(args) >= 2:
        scrape_multiple(args)
    elif len(args) == 1:
        scrape_njavtv(args[0])
    else:
        scrape_njavtv("STAR-471")
