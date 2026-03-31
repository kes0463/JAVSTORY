#!/usr/bin/env python3
"""
www.141jav.com/torrent/{slug} 직접 GET (하이픈 없는 소문자 슬러그).
프로젝트 루트: python scripts/test_141jav_crawl.py SNOS-152
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

from jav_site_test_common import (
    add_standard_args,
    extract_og_image,
    extract_title,
    collect_img_srcs,
    fetch_html,
    is_probably_torrent_missing,
    print_fetch_banner,
    print_fetch_result,
    resolve_proxy,
    torrent_slug_for_index_sites,
)


def main() -> int:
    p = argparse.ArgumentParser(description="141jav 토렌트 페이지 크롤 테스트")
    add_standard_args(p)
    args = p.parse_args()
    code = (args.code or "").strip()
    if not code:
        print("품번이 비었습니다.", file=sys.stderr)
        return 2

    slug = torrent_slug_for_index_sites(code)
    url = f"https://www.141jav.com/torrent/{slug}"
    host = (urlparse(url).hostname or "").lower()

    proxy = resolve_proxy(getattr(args, "proxy", None))
    print_fetch_banner("141jav", url)
    print(f"슬러그: {slug} (품번 {code})")
    if proxy:
        print(f"프록시: {proxy}")
    st, final, html, err = fetch_html(
        url, use_cloudscraper=args.cloudscraper, proxy=proxy
    )
    print_fetch_result(st, final, err)
    if html is None:
        return 1

    if is_probably_torrent_missing(st, html, host):
        print("\n판단: 해당 품번 페이지가 없거나 404에 가깝습니다.")
        return 0

    og = extract_og_image(html, final)
    title = extract_title(html)
    imgs = collect_img_srcs(html, final, limit=15)
    print("\n--- 파싱 ---")
    print(f"og:title: {title}")
    print(f"og:image: {og}")
    print("img 후보:")
    for u in imgs:
        print(f"  - {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
