import os
import sys
import time
import argparse
import cv2
import keyring

# NOTE:
# - 모듈 실행:   python -m core.scene_analysis_v2.pipeline ...
# - 파일 실행:   python core/scene_analysis_v2/pipeline.py ...
# 두 경우 모두 동작하도록 relative/absolute import를 모두 지원.
try:
    from .config import cfg
    from .step1_text_skeleton import create_text_skeleton, cross_validate_cuts_v21
    from .step2_signal_analysis import orchestrate_signal_analysis
    from .step3_vlm_strike import plan_vlm_calls_v21, execute_vlm_strikes
    from .step4_assembly import assemble_final_report_v21
except ImportError:  # pragma: no cover
    # 파일로 직접 실행될 때(__package__ 미설정) 대비
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _ROOT = os.path.dirname(os.path.dirname(_HERE))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from core.scene_analysis_v2.config import cfg
    from core.scene_analysis_v2.step1_text_skeleton import create_text_skeleton, cross_validate_cuts_v21
    from core.scene_analysis_v2.step2_signal_analysis import orchestrate_signal_analysis
    from core.scene_analysis_v2.step3_vlm_strike import plan_vlm_calls_v21, execute_vlm_strikes
    from core.scene_analysis_v2.step4_assembly import assemble_final_report_v21

from core.app_config import KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER, PROJECT_ROOT

class JAVSceneAnalysisPipelineV21:
    """
    [v2.1] 마스터 명세 준수 통합 파이프라인
    - Text-First (Whisper SRT)
    - Signal Analysis (Motion Dip & Audio)
    - VLM Precision Strike (GPT-4o)
    - Markdown Assembly
    """
    def __init__(self, video_path: str, srt_path: str, api_key: str = None):
        self.video_path = video_path
        self.srt_path = srt_path
        # API 키가 없으면 키링에서 시도
        self.api_key = api_key or keyring.get_password(KEYRING_SERVICE_NAME, "OPENAI_API_KEY")
        
        if not self.api_key:
             print("  ⚠️ Warning: API_KEY가 설정되지 않았습니다. VLM Strike 단계가 스킵될 수 있습니다.")

    def run(
        self,
        visual_cuts: list[float] = None,
        output_report_path: str = None,
        *,
        web_output_dir: str | None = None,
        screenshots_dir: str | None = None,
    ):
        start_time = time.time()
        print(f"🚀 [Pipeline v2.1] 분석 엔진 가동: {os.path.basename(self.video_path)}")
        
        # 기본 정보 확보
        cap = cv2.VideoCapture(self.video_path)
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        if not output_report_path:
             output_report_path = os.path.splitext(self.video_path)[0] + "_v21_report.md"

        # --- Phase 1: Text-First Skeleton ---
        skeleton = create_text_skeleton(self.srt_path, duration)
        
        # 시각적 컷 정보가 없으면 PySceneDetect(Content) 등으로 보완 가능 (여기서는 입력받음)
        if visual_cuts is None:
             # 임시 샘플 컷 (실제 연동 시 PySceneDetect 결과 전달)
             visual_cuts = [] 
             
        validation = cross_validate_cuts_v21(visual_cuts, skeleton, self.video_path)
        
        # --- Phase 2: Zero-VRAM Signal Analysis ---
        # 위임된(Delegated) 컷들에 대해 정밀 신호 분석 수행
        signal_events = orchestrate_signal_analysis(self.video_path, self.video_path, validation["delegated"])
        
        spa_root = str(PROJECT_ROOT)
        web_output_dir = web_output_dir or spa_root
        screenshots_dir = screenshots_dir if (screenshots_dir is not None) else os.path.join(spa_root, "screenshots")

        # --- Phase 3: VLM Precision Strike ---
        if self.api_key:
            planned_calls = plan_vlm_calls_v21(skeleton, signal_events)
            vlm_results = execute_vlm_strikes(
                self.video_path,
                planned_calls,
                self.api_key,
                screenshots_dir=screenshots_dir,
            )
        else:
            print("  🚫 [Step 3] API_KEY 누락으로 VLM 단계를 스킵합니다.")
            vlm_results = []

        # --- Phase 4: Full Assembly ---
        report_md = assemble_final_report_v21(
            skeleton["zones"],
            vlm_results,
            output_report_path,
            video_path=self.video_path,
            web_output_dir=web_output_dir,
        )
        
        total_dur = time.time() - start_time
        print(f"🏁 [Pipeline v2.1] 전체 공정 완료! (소요시간: {total_dur:.1f}s)")
        return output_report_path, report_md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="JAV Scene Analysis Pipeline v2.1 (video + srt → report + web_database + screenshots)",
    )
    parser.add_argument("video_path", help="입력 비디오 파일 경로(.mp4 등)")
    parser.add_argument("srt_path", help="입력 자막 파일 경로(.srt)")
    parser.add_argument(
        "--output-report-path",
        default=None,
        help="리포트 마크다운 저장 경로(미지정 시 비디오 옆에 *_v21_report.md)",
    )
    parser.add_argument(
        "--web-output-dir",
        default=None,
        help="web_database.json/js 생성 디렉터리(미지정 시 PROJECT_ROOT)",
    )
    parser.add_argument(
        "--screenshots-dir",
        default=None,
        help="VLM 성공 시 저장할 스크린샷 디렉터리(미지정 시 PROJECT_ROOT/screenshots)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenAI API Key(미지정 시 keyring에서 OPENAI_API_KEY 조회)",
    )

    args = parser.parse_args()
    pipeline = JAVSceneAnalysisPipelineV21(args.video_path, args.srt_path, api_key=args.api_key)
    pipeline.run(
        output_report_path=args.output_report_path,
        web_output_dir=args.web_output_dir,
        screenshots_dir=args.screenshots_dir,
    )
