from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal as pyqtSignal


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


class HighlightWorker(QThread):
    """영상에서 하이라이트 클립을 추출하는 백그라운드 워커(사용자 수동 트리거)."""

    finished = pyqtSignal(bool, str)  # success, message
    progressUpdated = pyqtSignal(int)  # 0~100 퍼센트 진행률

    def __init__(self, product_code: str, video_path: str, output_dir: str):
        super().__init__()
        self.product_code = (product_code or "").strip().upper()
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)

    def run(self):
        try:
            run_id = f"{self.product_code}_HL_{int(time.time() * 1000)}"
            if not self.video_path.exists():
                self.finished.emit(False, f"원본 영상을 찾을 수 없습니다: {self.video_path}")
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)

            from javstory.library.highlight.highlight import create_highlight_video

            res_path = create_highlight_video(
                product_code=self.product_code,
                video_path=self.video_path,
                output_dir=self.output_dir,
                progress_callback=lambda p: self.progressUpdated.emit(int(p)),
            )

            if res_path and res_path.exists():
                self.finished.emit(True, "하이라이트 영상이 생성되었습니다!")
            else:
                self.finished.emit(False, "하이라이트 생성 중 하이라이트 구간을 찾지 못했거나 오류가 발생했습니다.")

            _dbg_log(
                run_id,
                "highlight_worker.finished",
                "gui/workers/highlight_worker.py",
                "highlight done",
                {"ok": bool(res_path and res_path.exists()), "out_dir": str(self.output_dir)},
            )
        except Exception as e:
            msg = f"에러 발생: {str(e)}"
            self.finished.emit(False, msg)

