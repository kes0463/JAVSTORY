import os
import time
import cv2
import keyring
from .config import cfg
from .step1_text_skeleton import create_text_skeleton, cross_validate_cuts_v21
from .step2_signal_analysis import orchestrate_signal_analysis
from .step3_vlm_strike import plan_vlm_calls_v21, execute_vlm_strikes
from .step4_assembly import assemble_final_report_v21

from core.app_config import KEYRING_SERVICE_NAME, KEYRING_ACCOUNT_OPENROUTER

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

    def run(self, visual_cuts: list[float] = None, output_report_path: str = None):
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
        
        # --- Phase 3: VLM Precision Strike ---
        if self.api_key:
            planned_calls = plan_vlm_calls_v21(skeleton, signal_events)
            vlm_results = execute_vlm_strikes(self.video_path, planned_calls, self.api_key)
        else:
            print("  🚫 [Step 3] API_KEY 누락으로 VLM 단계를 스킵합니다.")
            vlm_results = []

        # --- Phase 4: Full Assembly ---
        report_md = assemble_final_report_v21(skeleton["zones"], vlm_results, output_report_path)
        
        total_dur = time.time() - start_time
        print(f"🏁 [Pipeline v2.1] 전체 공정 완료! (소요시간: {total_dur:.1f}s)")
        return output_report_path, report_md

if __name__ == "__main__":
    # 단위 테스트 코드 (예시)
    print("JAV Scene Analysis Pipeline v2.1 Module Loaded.")
