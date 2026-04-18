"""구간 [start_sec, end_sec] 내 동등 분할 시각 — 짧은 구간·최소 간격 정책."""

from __future__ import annotations


def equal_split_seconds(
    start_sec: float,
    end_sec: float,
    n: int,
    *,
    min_gap_sec: float = 0.5,
) -> list[float]:
    """
    n개의 스틸 시각을 구간 안에서 균등 배치.
    - n < 1 이면 []
    - 구간 길이 <= 0 이면 [start_sec] 만 (n>=1)
    - 길이가 짧아 겹치면 min_gap_sec을 적용해 최대한 벌리고, 불가능하면 1점만.
    """
    if n < 1:
        return []
    if end_sec < start_sec:
        start_sec, end_sec = end_sec, start_sec
    length = end_sec - start_sec
    if length <= 0:
        return [start_sec] * min(n, 1) if n >= 1 else []

    if n == 1:
        return [start_sec + length / 2.0]

    # 이상적 균등: 경계에서 약간 안쪽
    raw = [start_sec + (i + 1) * length / (n + 1) for i in range(n)]

    if n <= 1 or length >= min_gap_sec * (n - 1):
        return raw

    # 짧은 구간: 중앙 하나 또는 min_gap으로 벌린 소수 점
    if length < min_gap_sec:
        return [start_sec + length / 2.0]

    # 가능한 한 많은 점을 min_gap으로 배치
    times: list[float] = []
    t = start_sec + min_gap_sec / 2
    while t <= end_sec - min_gap_sec / 2 and len(times) < n:
        times.append(t)
        t += min_gap_sec
    if not times:
        times = [start_sec + length / 2.0]
    return times[:n]
