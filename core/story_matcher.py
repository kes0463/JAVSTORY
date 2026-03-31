import json
import os
import asyncio
from typing import List, Dict, Any, Optional

import keyring

from core.app_config import KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER
from core.database import get_db_session, upsert_jav_metadata

class StoryMatcher:
    """
    [Phase 4] 투트랙 AI 보조 분석기.
    - 로컬 GPU(faster-whisper) 기반 STT + 클라우드(OpenRouter) 기반 요약.
    - 타임스탬프 기반 씬 매칭 로직 탑재.
    """

    def __init__(self, video_path: str, product_code: str):
        self.video_path = video_path
        self.product_code = product_code
        self.session = get_db_session()

    def _get_api_key(self):
        return keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER)

    def transcribe_local(self) -> List[Dict[str, Any]]:
        """
        [Gatekeeper 통합] Whisper.py의 통합 파이프라인 호출.
        - 내부에서 로컬 자막(.ja.srt) 유무를 먼저 확인하고, 없으면 STT 수행 후 자동 저장함.
        """
        from core.Whisper import process_video_to_segments
        from core.app_config import MEDIA_ROOT
        
        # 1. 고성능 STT 분석 (Whisper.py 내부에서 게이트키퍼 및 저장 처리됨)
        print(f"[StoryMatcher] 고성능 STT 분석 수행: {self.product_code}")
        output_dir = MEDIA_ROOT / self.product_code / "whisper_tmp"
        
        segments = process_video_to_segments(str(self.video_path), str(output_dir))
        
        # 2. 분석 결과를 씬 매칭용 Dict 형식으로 변환
        results = []
        for segment in segments:
            results.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "mid": (segment.start + segment.end) / 2,
                "needs_review": segment.needs_review,
                "review_reason": getattr(segment, "review_reason", [])
            })
        
        return results

    def transcribe_only(self) -> List[Dict[str, Any]]:
        return self.transcribe_local()

    def match_text_to_scenes(self, segments: List[Dict[str, Any]], scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for seg in segments:
            best_scene = None
            max_overlap = -1.0
            
            for scene in scenes:
                overlap_start = max(seg["start"], scene["start_time"])
                overlap_end = min(seg["end"], scene["end_time"])
                overlap_duration = max(0, overlap_end - overlap_start)
                
                if overlap_duration > max_overlap:
                    max_overlap = overlap_duration
                    best_scene = scene

            if best_scene and max_overlap > 0:
                current = best_scene.get("raw_text", "")
                best_scene["raw_text"] = (current + " " + seg["text"]).strip()
                
                # [v2.0] 검토 필요 플래그 전파
                if seg.get("needs_review"):
                    best_scene["needs_review"] = True
                    reasons = best_scene.get("review_reasons", [])
                    reasons.extend(seg.get("review_reason", []))
                    best_scene["review_reasons"] = list(set(reasons))
        return scenes

    async def summarize_with_llm_v2(self, matched_scenes: List[Dict[str, Any]], model_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """[Phase 5] AIAnalyzer를 이용한 하이엔드 통합 분석 (Async)"""
        from core.ai_analyzer import AIAnalyzer
        from core.database import JAVMetadata
        
        api_key = self._get_api_key()
        if not api_key:
            return {"error": "API 키가 없습니다."}

        row = self.session.query(JAVMetadata).filter_by(product_code=self.product_code).first()
        metadata = {
            "title": row.title if row else "알 수 없음",
            "actors": row.actors if row else "알 수 없음",
            "genres": row.genres if row else "알 수 없음"
        }

        analyzer = AIAnalyzer(api_key)
        # AIAnalyzer.analyze는 이제 async임
        return await analyzer.analyze(matched_scenes, metadata, tier_override=model_override)

    async def finalize_story_matching(self, scenes: List[Dict[str, Any]], segments: List[Dict[str, Any]], model_override: Optional[Dict[str, Any]] = None):
        """하이엔드 통합 분석 수행 (Async)"""
        from core.llm_engine import AllTiersExhaustedError

        if not scenes:
            print("[StoryMatcher] 매칭할 씬 데이터가 없습니다.")
            return

        matched_scenes = self.match_text_to_scenes(segments, scenes)

        print(f"[StoryMatcher] 하이엔드 분석(V2) 시작: {self.product_code}")
        try:
            # summarize_with_llm_v2 호출 시 await 사용
            analysis_result = await self.summarize_with_llm_v2(matched_scenes, model_override=model_override)
            
            relationship_analysis = analysis_result.get("relationship_analysis", "분석 실패")
            v2_scenes = analysis_result.get("scenes", [])
            
            for i, scene in enumerate(matched_scenes):
                if i < len(v2_scenes):
                    v2_data = v2_scenes[i]
                    if "summary" in scene:
                        scene["legacy_summary"] = scene["summary"]
                    
                    scene["summary"] = "\n".join(v2_data.get("three_line_summary", []))
                    scene["translated_content"] = v2_data.get("translated_content", "")
                    scene["three_line_summary"] = v2_data.get("three_line_summary", [])
            
            extra_data = {
                "scene_summaries": matched_scenes,
                "character_relationships": relationship_analysis,
                "analysis_version": "v2_ai_analyzer",
                "analysis_status": "done"
            }
            upsert_jav_metadata(self.session, product_code=self.product_code, extra=extra_data)
            print(f"[StoryMatcher] 하이엔드 분석 및 요약 완료: {self.product_code}")

        except AllTiersExhaustedError:
            print(f"⚠️ [StoryMatcher] 모든 AI 모델이 분석에 실패했습니다. 최소 요약 로직으로 폴백합니다.")
            self._fallback_to_v1_summaries(matched_scenes)
        except Exception as e:
            print(f"❌ [StoryMatcher] 분석 중 치명적 오류: {e}")
            upsert_jav_metadata(self.session, product_code=self.product_code, extra={"analysis_status": "failed"})

    def _fallback_to_v1_summaries(self, matched_scenes: List[Dict[str, Any]]):
        for scene in matched_scenes:
            if "summary" not in scene:
                scene["summary"] = "AI 분석 실패 (Raw 데이터 보존)"
        upsert_jav_metadata(self.session, product_code=self.product_code, 
                            extra={"scene_summaries": matched_scenes, "analysis_status": "done_partial"})

    def run_analysis(self, model_override: Optional[Dict] = None):
        """기존 동기식 실행 파이프라인 (내부에서 asyncio.run 사용)"""
        try:
            from core.database import JAVMetadata
            row = self.session.query(JAVMetadata).filter_by(product_code=self.product_code).first()
            scenes = row.scene_summaries if row else []
            segments = self.transcribe_only()
            # 비동기 메서드를 동기적으로 실행
            asyncio.run(self.finalize_story_matching(scenes, segments, model_override=model_override))
        except Exception as e:
            print(f"[StoryMatcher] 오류 발생: {e}")
        finally:
            self.session.close()

if __name__ == "__main__":
    pass
