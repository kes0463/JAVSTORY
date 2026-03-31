"""파이프라인 스텁: 크롤러는 하이브리드 구현 연결, 나머지는 더미."""
from __future__ import annotations

from core.hybrid_crawler import run_crawler_phase


def run_whisper_phase(*args, **kwargs) -> None:
    print("해당 모듈 실행됨")


def run_llm_phase(*args, **kwargs) -> None:
    print("해당 모듈 실행됨")


def run_scene_detect_phase(*args, **kwargs) -> None:
    print("해당 모듈 실행됨")


def run_full_pipeline_dummy(video_paths: list[str]) -> None:
    """배치 시작 시 순서만 보여 주는 더미 파이프라인."""
    for _path in video_paths:
        run_crawler_phase(path=_path)
        run_scene_detect_phase(path=_path)
        run_whisper_phase(path=_path)
        run_llm_phase(path=_path)
