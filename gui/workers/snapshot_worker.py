
from PySide6.QtCore import QThread, Signal as pyqtSignal
from pathlib import Path
import os
import json
import time

class SnapshotWorker(QThread):
    """영상에서 고속 CUDA 하드웨어 가속으로 스냅샷을 추출하는 백그라운드 워커"""
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, product_code: str, video_path: str, output_dir: str):
        super().__init__()
        self.product_code = product_code
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.target_count = 150 # 기본값

    def run(self):
        try:
            if not self.video_path.exists():
                self.finished.emit(False, f"영상 파일을 찾을 수 없습니다: {self.video_path}")
                return

            self.output_dir.mkdir(parents=True, exist_ok=True)
            from javstory.library.stills.extract import extract_snapshots_auto_adaptive, probe_video_duration_seconds, suggest_snapshot_target_count
            from javstory.utils.derived_cache import is_up_to_date, mark_up_to_date
            from javstory.utils.perf_log import perf_span
            
            dur = probe_video_duration_seconds(self.video_path)
            self.target_count = suggest_snapshot_target_count(dur)

            meta_path = self.output_dir / ".snapshot.meta.json"
            params = {"prefix": "snapshot", "quality": 85}

            existing = list(self.output_dir.glob("snapshot_*.jpg"))
            if len(existing) >= int(self.target_count) and is_up_to_date(
                meta_path=meta_path,
                inputs={"video": self.video_path},
                params=params,
            ):
                self.progress.emit(self.target_count, self.target_count)
                self.finished.emit(True, f"스냅샷은 이미 최신입니다. ({len(existing)}개)")
                return

            # 진행률 콜백 (FFmpeg 로그 파싱 데이터 전달)
            def on_progress(percent: int):
                current = int((percent / 100.0) * self.target_count)
                self.progress.emit(current, self.target_count)

            # [핵심] 핵심 엔진 호출 (내부에서 CUDA 하드웨어 가속 사용)
            with perf_span(
                "snapshots.extract",
                product_code=self.product_code,
                video=str(self.video_path),
                out_dir=str(self.output_dir),
                target_count=int(self.target_count),
            ):
                res = extract_snapshots_auto_adaptive(
                    self.video_path,
                    self.output_dir,
                    prefix="snapshot",
                    quality=85,
                    progress_callback=on_progress,
                )
            
            if res:
                mark_up_to_date(meta_path=meta_path, inputs={"video": self.video_path}, params=params)
                self.progress.emit(self.target_count, self.target_count)
                self.finished.emit(True, f"{len(res)}개의 스냅샷을 CUDA 가속으로 추출 완료했습니다.")
            else:
                self.finished.emit(False, "스냅샷 생성에 실패했습니다. FFmpeg 출력을 확인하세요.")

        except Exception as e:
            self.finished.emit(False, f"에러 발생: {str(e)}")
