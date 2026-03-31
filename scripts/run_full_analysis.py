import os
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.analyzer_coordinator import run_parallel_analysis
from core.database import get_db_session, JAVMetadata
from core.model_selector import select_model_interactive

def main():
    """
    [Phase 5] 하이엔드 통합 분석 프로세스 원클릭 실행 스크립트.
    """
    # 1. 대상 영상 설정
    # [자동 감지] D 드라이브에 실제 파일이 있다면 우선 사용
    video_path = r"D:\STAR-471_output.mp4"
    if not os.path.exists(video_path):
        video_path = r"sample_video.mp4" 
        
    product_code = "STAR-471"
    
    if not os.path.exists(video_path):
        print(f"⚠️ 경고: '{video_path}' 파일을 찾을 수 없습니다.")
        print(f"실제 영상 분석을 위해 'scripts/run_full_analysis.py'의 video_path를 수정해 주세요.")
        
        # 실제 데이터가 없어도 DB 구조 테스트는 가능하도록 함
        session = get_db_session()
        row = session.query(JAVMetadata).filter_by(product_code=product_code).first()
        if not row:
            from core.database import upsert_jav_metadata
            upsert_jav_metadata(session, product_code=product_code, 
                                extra={"analysis_status": "pending"})
        session.close()
        return  # 영상이 없으면 분석 프로세스를 중단하여 잘못된 성공 메시지 방지

    # 2. 분석 모드 선택 UI
    print("\n" + "=" * 60)
    print("  ⭐ JAV 하이엔드 분석 시스템 (Step 5)")
    print("=" * 60)
    print("  [1] 자동 폴백 모드 (기본: DeepSeek -> Hermes -> Gemini -> Local)")
    print("  [2] 수동 선택 모드 (Claude 3.5 Sonnet 프리미엄 분석 포함)")
    print("=" * 60)
    
    mode = input("\n  분석 모드 선택 [1/2] (기본: 1): ").strip()
    
    model_override = None
    if mode == "2":
        model_override = select_model_interactive()
        print(f"\n  👉 선택된 모델로 분석을 진행합니다: {model_override.get('label', model_override.get('model'))}")
    else:
        print("\n  🚀 자동 폴백 모드로 분석을 시작합니다.")

    # 3. 병렬 분석 시작
    print(f"🚀 [{product_code}] 병렬 분석 프로세스 시동...")
    try:
        # 코디네이터 호출 (모델 오버라이드 전달)
        run_parallel_analysis(video_path, product_code, model_override=model_override)
        print(f"\n✅ 분석이 성공적으로 완료되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 분석 도중 오류 발생: {e}")

if __name__ == "__main__":
    main()
