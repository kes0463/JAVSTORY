from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal as pyqtSignal


class PreviewWorker(QThread):
    """Golden Preview(WebP) 생성 워커 (Harvest 후 자동/백필용)."""

    resultReady = pyqtSignal(bool, str)  # success, message
    progressUpdated = pyqtSignal(int)  # 0~100

    def __init__(self, product_code: str, video_path: str, output_path: str):
        super().__init__()
        self.product_code = (product_code or "").strip().upper()
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)

    def run(self):
        try:
            if not self.video_path.exists():
                self.resultReady.emit(False, f"원본 영상을 찾을 수 없습니다: {self.video_path}")
                return

            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            from javstory.library.highlight.video_preview import create_golden_preview
            from javstory.utils.derived_cache import is_up_to_date, mark_up_to_date
            from javstory.utils.perf_log import perf_span

            meta_path = self.output_path.with_suffix(self.output_path.suffix + ".meta.json")
            params = {"duration_sec": 8.0}
            if self.output_path.is_file() and is_up_to_date(
                meta_path=meta_path,
                inputs={"video": self.video_path},
                params=params,
            ):
                self.progressUpdated.emit(100)
                self.resultReady.emit(True, "프리뷰(WebP)는 이미 최신입니다.")
                return

            with perf_span(
                "preview.create",
                product_code=self.product_code,
                video=str(self.video_path),
                out=str(self.output_path),
            ):
                res = create_golden_preview(
                    product_code=self.product_code,
                    video_path=self.video_path,
                    output_path=self.output_path,
                    progress_callback=lambda p: self.progressUpdated.emit(int(p)),
                    duration_sec=8.0,
                )
            if res and res.is_file():
                mark_up_to_date(meta_path=meta_path, inputs={"video": self.video_path}, params=params)
                self.resultReady.emit(True, "프리뷰(WebP)가 생성되었습니다!")
            else:
                self.resultReady.emit(False, "프리뷰 생성에 실패했습니다.")
        except Exception as e:
            self.resultReady.emit(False, f"에러 발생: {e}")

