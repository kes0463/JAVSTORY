import json
import re
from typing import List, Dict, Any

# [Phase 5] 모델 티어별 청킹 및 지연 설정
CHUNK_CONFIG = {
    "paid": {
        "max_lines": 300,
        "max_tokens": 12000,
        "sleep_sec": 1,
    },
    "free": {
        "max_lines": 100,
        "max_tokens": 4000,
        "sleep_sec": 10,  # Free 모델은 레이트 리밋이 엄격하므로 길게 설정
    },
    "local": {
        "max_lines": 500,
        "max_tokens": 16000,
        "sleep_sec": 0,   # 로컬 모델은 대기 불필요 (VRAM OOM 주의)
    }
}

def estimate_tokens(text: str) -> int:
    """
    경량 토큰 추정기.
    - 한국어/일본어 특성을 고려하여 글자 수 기반 근사치 계산 (1글자 ~= 1.5 ~ 2.0 토큰)
    - 넉넉하게 계산하여 OOM 및 Context Limit 방어.
    """
    if not text:
        return 0
    # 공백 포함 글자 수 * 2배 (한글/일어 가중치) + 특수문자 보정
    return int(len(text) * 2.0)

def chunk_by_scene(scenes: List[Dict[str, Any]], tier: str = "free") -> List[List[Dict[str, Any]]]:
    """
    씬(Scene) 경계를 엄수하며 텍스트를 분할하는 하이브리드 청커.
    - 하나의 씬 데이터가 두 개의 청크로 쪼개지지 않도록 통합 관리.
    - Tier별 CHUNK_CONFIG 설정을 준수함.
    """
    config = CHUNK_CONFIG.get(tier, CHUNK_CONFIG["free"])
    max_lines = config["max_lines"]
    max_tokens = config["max_tokens"]

    chunks = []
    current_chunk = []
    current_lines = 0
    current_tokens = 0

    for scene in scenes:
        scene_text = scene.get("raw_text", "")
        # 씬 내 대화 줄 수 계산
        scene_lines = len(scene_text.splitlines()) if scene_text else 1
        scene_tokens = estimate_tokens(scene_text)

        # 1. 단일 씬이 너무 큰 경우 (극단적 상황 대응)
        if scene_tokens > max_tokens or scene_lines > max_lines:
            # 이미 현재 청크에 데이터가 있다면 일단 마무리
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_lines = 0
                current_tokens = 0
            
            # 이 씬 자체가 하나의 청크가 됨 (강제 수용)
            chunks.append([scene])
            continue

        # 2. 현재 청크에 추가 가능한지 확인
        if (current_lines + scene_lines > max_lines) or (current_tokens + scene_tokens > max_tokens):
            # 한도를 초과하면 현재까지의 청크를 저장하고 새로 시작
            if current_chunk:
                chunks.append(current_chunk)
            
            current_chunk = [scene]
            current_lines = scene_lines
            current_tokens = scene_tokens
        else:
            # 한도 내라면 현재 청크에 추가
            current_chunk.append(scene)
            current_lines += scene_lines
            current_tokens += scene_tokens

    # 남은 데이터 처리
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

if __name__ == "__main__":
    # 간단한 테스트
    test_scenes = [
        {"scene_index": 1, "raw_text": "대사 1\n대사 2\n대사 3"},
        {"scene_index": 2, "raw_text": "대사 4\n대사 5\n대사 6\n대사 7"},
        {"scene_index": 3, "raw_text": "매우 긴 대사..." * 50}
    ]
    result = chunk_by_scene(test_scenes, tier="free")
    print(f"Total Chunks: {len(result)}")
    for i, chunk in enumerate(result):
        idx_list = [s["scene_index"] for s in chunk]
        print(f"Chunk {i+1}: Scenes {idx_list}")
