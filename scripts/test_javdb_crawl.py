#!/usr/bin/env python3
"""
javdb.com 검색 → 첫 상세(/v/…) 페이지까지 GET 후 표지 후보 출력.
프로젝트 루트: python scripts/test_javdb_crawl.py ABW-138
"""
from __future__ import annotations

import argparse
import re
import sys
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

# 동일 디렉터리 공통 (패키지 아님)
from jav_site_test_common import (
    add_standard_args,
    extract_og_image,
    extract_title,
    collect_img_srcs,
    fetch_html,
    print_fetch_banner,
    print_fetch_result,
    resolve_proxy,
)


def first_detail_url_from_search(html: str, search_page_url: str) -> str | None:
    """검색 결과 HTML에서 첫 /v/… 링크."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if re.match(r"^/v/[a-zA-Z0-9_-]+$", href):
            return urljoin(search_page_url, href)
    # 백업: raw regex
    m = re.search(r'href="(/v/[a-zA-Z0-9_-]+)"', html)
    if m:
        return urljoin(search_page_url, m.group(1))
    return None


def main() -> int:
    p = argparse.ArgumentParser(description="javdb 검색·상세 페이지 크롤 테스트")
    add_standard_args(p)
    args = p.parse_args()
    code = (args.code or "").strip()
    if not code:
        print("품번이 비었습니다.", file=sys.stderr)
        return 2

    use_cs = args.cloudscraper
    proxy = resolve_proxy(getattr(args, "proxy", None))
    q = quote(code)
    search_url = f"https://javdb.com/search?q={q}&f=all"

    print_fetch_banner("javdb - search", search_url)
    if proxy:
        print(f"프록시: {proxy}")
    st, final, html, err = fetch_html(
        search_url, use_cloudscraper=use_cs, proxy=proxy
    )
    print_fetch_result(st, final, err)
    if html is None:
        return 1

    detail = first_detail_url_from_search(html, final)
    if not detail:
        print("\n검색 결과에서 /v/ 상세 링크를 찾지 못했습니다 (품번 없음 또는 HTML 구조 변경).")
        print(f"본문 길이: {len(html)} bytes")
        return 0

    print(f"\n첫 상세 링크: {detail}")
    print_fetch_banner("javdb - detail", detail)
    st2, final2, html2, err2 = fetch_html(
        detail, use_cloudscraper=use_cs, proxy=proxy
    )
    print_fetch_result(st2, final2, err2)
    if html2 is None:
        return 1

    og = extract_og_image(html2, final2)
    title = extract_title(html2)
    imgs = collect_img_srcs(html2, final2, limit=15)
    print("\n--- 파싱 ---")
    print(f"og:title: {title}")
    print(f"og:image: {og}")
    print("img 후보:")
    for u in imgs:
        print(f"  - {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
