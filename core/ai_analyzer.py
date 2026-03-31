import json
import hashlib
import re
import os
import asyncio
from typing import List, Dict, Any, Optional
from core.llm_engine import MultiTierRouter, AllTiersExhaustedError, JSONValidationError
from core.chunker import chunk_by_scene, CHUNK_CONFIG
from core.app_config import PROJECT_ROOT

class AIAnalyzer:
    """
    [Phase 5] 세계 최고의 일본 성인 미디어 전문 분석가 페르소나 엔진.
    - 하이브리드 청킹 통합 (Scene Chunker 연동).
    - Chain of Thought (CoT) 강제 프롬프트.
    - 강력한 정규식 기반 JSON 파싱 및 자가 수리.
    """
    def __init__(self, api_key: str):
        self.router = MultiTierRouter(api_key)
        self.cache_dir = PROJECT_ROOT / "data" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, scene_data: List[Dict], metadata: Dict) -> str:
        content = json.dumps({"scenes": scene_data, "meta": metadata}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get_system_prompt(self) -> str:
        """하이엔드 페르소나 및 CoT 가이드라인 (환각 필터링 포함)"""
        return """너는 세계 최고의 일본 성인 미디어 전문 분석가이자 한국어 번역가야.
너의 임무는 단순 번역을 넘어 대화의 맥락과 인물 관계를 파악하여 가장 자연스러운 한국어 페르소나를 입히는 것이다.

[Whisper STT 환각 필터링 지침 - 매우 중요]
입력된 STT 결과값에서 다음 세 가지 유형의 '환각' 데이터는 분석 및 번역에서 **완전히 제외**하라:
1. 기계적 반복: 동일 단어/문장 3회 이상 기계적 반복 (단, "はい", "ねえ" 등 실제 대화 맥락은 유지).
2. 메타성 문구: 극 중 상황과 무관한 유튜브/방송 크레딧("시청 감사", "자막 제작", "문의는" 등).
3. 의성어 및 오인식: 신음소리(모음 나열)의 문자화 또는 문맥과 전혀 무관한 뉴스/드라마 대사 조각.

[v2.0] 만약 특정 세그먼트가 'needs_review' 상태라면, 해당 구간은 높은 확률로 환각(반복 발화 또는 기술적 노이즈)일 가능성이 크니 맥락상 부자연스럽다면 과감히 삭제하라.

[Chain of Thought (CoT) 프로세스 - 반드시 다음 순서를 거쳐라]
1. 인물 관계 및 호칭 분석 (Relationship & Honorifics Mapping): 제공된 배우 정보와 대사 맥락을 조합해 인물 간의 사회적 관계(상사-부하, 선후배, 부부, 모녀 등)를 정의하고, 일본 주어/호칭(오빠, 센배, 오마에 등)의 적절한 한국어 로컬라이징 방향을 설정한다.
2. 페르소나 적용 정밀 번역 (Persona-Enforced Translation): 1단계에서 정의된 말투를 유지하며 대사를 초정밀 번역한다. 성인 미디어 특유의 감정선이 누락되지 않게 생동감을 불어넣는다. **위의 환각 필터링 지침을 적용하여 불필요한 대사는 생략한다.**
3. 씬별 요약 (Scene Summary): 해당 씬의 핵심 줄거리와 배우의 감정 변화를 3문장 이내로 정리한다.

[출력 규격 - 반드시 순수 JSON 포맷 준수]
- 마크다운 설명이나 ```json 태그 없이 순수 JSON 객체만 출력해라.
{
  "relationship_analysis": "인물 간 관계 요약 및 말투 설정 근거 (한국어로 작성)",
  "scenes": [
    {
      "scene_index": 1,
      "translated_content": "페르소나가 반영된 한국어 번역 대사 전체 (환각 제거됨)",
      "three_line_summary": [
        "사건 발생 요약 1",
        "감정선 변화 요약 2",
        "씬 마무리 요약 3"
      ]
    }
  ]
}
"""

    def validate_json_robustly(self, raw_text: str) -> Dict[str, Any]:
        """정규식을 활용한 강력한 JSON 추출 및 검증"""
        # 1. { } 사이의 텍스트만 추출 (마크다운 및 쓰레기 텍스트 제거)
        match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
        if not match:
             raise JSONValidationError("JSON 형식을 찾을 수 없습니다. (브라켓 누락)")
        
        json_str = match.group(1)
        
        # 2. 제어 문자 제거 (줄바꿈 외의 깨진 문자들)
        json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
        
        try:
            data = json.loads(json_str)
            if "relationship_analysis" in data and "scenes" in data:
                return data
            raise JSONValidationError("필수 키(relationship_analysis, scenes)가 누락되었습니다.")
        except Exception as e:
            raise JSONValidationError(f"JSON 파싱 실패: {str(e)}")

    async def analyze(self, scene_data: List[Dict[str, Any]], metadata: Dict[str, Any], tier_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        [Phase 5 핵심] 씬 기반 하이엔드 분석.
        1. 티어 결정 및 청킹 수행.
        2. 비동기 순차 LLM 호출 (지연 대기 포함).
        3. 결과 병합 및 캐싱.
        """
        # 티어 결정 (Override가 있으면 paid/custom으로 간주, 없으면 free/low 로직)
        is_paid = (tier_override is not None)
        tier_mode = "paid" if is_paid else "free"
        
        # 1. 청킹 (Scene Chunker 연동)
        chunks = chunk_by_scene(scene_data, tier=tier_mode)
        print(f"  [Analyzer] 데이터가 {len(chunks)}개의 청크로 분할되었습니다. (Mode: {tier_mode})")

        # 2. 캐시 확인 (전체 통합 키)
        cache_key = self.get_cache_key(scene_data, metadata)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            print(f"  [Analyzer] 캐시 적중! 완료된 분석 결과 로드.")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # 3. 비동기 순차 처리
        system_prompt = self.get_system_prompt()
        meta_context = json.dumps(metadata, ensure_ascii=False, indent=2)
        sleep_sec = CHUNK_CONFIG[tier_mode]["sleep_sec"]

        try:
            raw_responses = await self.router.process_chunks(
                chunks, system_prompt, meta_context, 
                tier_override=tier_override, sleep_sec=sleep_sec
            )

            # 4. 결과 병합 (Relationship은 첫 번째 결과물 활용)
            final_data = {
                "relationship_analysis": "",
                "scenes": []
            }

            for idx, raw in enumerate(raw_responses):
                try:
                    chunk_result = self.validate_json_robustly(raw)
                    if idx == 0:
                        final_data["relationship_analysis"] = chunk_result["relationship_analysis"]
                    
                    final_data["scenes"].extend(chunk_result["scenes"])
                except JSONValidationError as e:
                    print(f"  ⚠️ [Analyzer] Chunk {idx+1} JSON 오류 무시: {e}")
                    # 실패한 청크에 대한 최소 빈 데이터 삽입 가능
                    continue

            # 5. 캐싱 및 반환
            if final_data["scenes"]:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                return final_data
            else:
                raise AllTiersExhaustedError("모든 청크의 분석 결과가 유효한 JSON이 아닙니다.")

        except Exception as e:
            print(f"  [Analyzer] 심각한 분석 오류: {e}")
            raise
