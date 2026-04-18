from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import time
import os
import json

# region agent log
_DEBUG_LOG_PATH = Path("D:/App/JAVSTORY/debug-210e54.log")

def _dbg_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "210e54",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion agent log

class DigestWorker(QThread):
    """영상에서 60배속 MP4 타임랩스를 추출하는 백그라운드 워커"""
    finished = pyqtSignal(bool, str) # success, message
    progressUpdated = pyqtSignal(int) # 0~100 퍼센트 진행률

    def __init__(self, product_code: str, video_path: str, output_path: str):
        super().__init__()
        self.product_code = product_code
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)

    def run(self):
        try:
            run_id = f"{self.product_code}_{int(time.time() * 1000)}"
            if not self.video_path.exists():
                self.finished.emit(False, f"원본 영상을 찾을 수 없습니다: {self.video_path}")
                return

            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 기존 타임랩스가 찌꺼기로 있다면 제거
            if self.output_path.exists():
                try: os.remove(self.output_path)
                except: pass

            from javstory.library.stills.digest import create_digest_video
            
            res_path = create_digest_video(
                video_path=self.video_path,
                output_path=self.output_path,
                speed=60,  # 60배속
                width=860,  # 해상도 옵션
                progress_callback=lambda p: self.progressUpdated.emit(p)
            )
            
            if res_path and res_path.exists():
                self.finished.emit(True, "안정적인 타임랩스 다이제스트가 생성되었습니다!")
            else:
                self.finished.emit(False, "타임랩스 생성 중 문제가 발생했습니다.")
                
        except Exception as e:
            msg = f"에러 발생: {str(e)}"
            self.finished.emit(False, msg)
