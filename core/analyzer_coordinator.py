import time
from concurrent.futures import ThreadPoolExecutor
from core.scene_analyzer import SceneAnalyzer
from core.story_matcher import StoryMatcher
from core.database import get_db_session, upsert_jav_metadata

def run_parallel_analysis(video_path: str, product_code: str, model_override: dict = None):
    """
    [Phase 5] 씬 분석(CPU)과 Whisper STT(GPU)를 병렬로 실행하는 코디네이터.
    model_override: 사용자 선택 모델 (Manual Mode 시 활용)
    """
    start_time = time.time()
    print(f"[Coordinator] 병렬 분석 시작: {product_code}")
    
    session = get_db_session()
    analyzer = SceneAnalyzer(video_path, product_code)
    matcher = StoryMatcher(video_path, product_code)

    try:
        # 1. 상태를 'processing'으로 업데이트
        upsert_jav_metadata(session, product_code=product_code, extra={"analysis_status": "processing"})

        # 2. 병렬 실행 (씬 분석 & Whisper)
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_scenes = executor.submit(analyzer.run_analysis_only) # CPU/FFmpeg 위주
            future_whisper = executor.submit(matcher.transcribe_only)  # GPU(Whisper) 위주
            
            # 두 작업이 완료될 때까지 대기
            scenes = future_scenes.result()
            segments = future_whisper.result()

        # 3. 매칭 및 하이엔드 통합 분석 (V2)
        # 의존성 단계이므로 순차 실행. StoryMatcher 내부에서 AIAnalyzer를 호출함.
        print(f"[Coordinator] 병렬 분석 완료(소요시간: {time.time() - start_time:.1f}s). 하이엔드 분석(V2) 진행.")
        import asyncio
        asyncio.run(matcher.finalize_story_matching(scenes, segments, model_override=model_override))
        
        # 4. 최종 상태 업데이트
        upsert_jav_metadata(session, product_code=product_code, extra={"analysis_status": "done"})
        print(f"[Coordinator] 전체 분석 프로세스 성공: {product_code}")

    except Exception as e:
        session.rollback()
        print(f"[Coordinator] 분석 중 오류 발생: {e}")
        upsert_jav_metadata(session, product_code=product_code, extra={"analysis_status": "failed"})
        # 씬 분석기 내부에서 실패 시 파일 정리를 수행하지만, 여기서도 보조적으로 수행 가능
        analyzer._cleanup_failure()
        raise  # 메인 스크립트에서 오류를 감지할 수 있도록 재발생
    finally:
        session.close()

if __name__ == "__main__":
    # 예시 실행 코드
    # run_parallel_analysis("test_video.mp4", "STAR-471")
    pass
