"""백그라운드 스냅샷 추출 전담 큐 매니저."""

from __future__ import annotations

import logging
import threading
import queue
from pathlib import Path

from javstory.library.stills.extract import extract_snapshots_auto_adaptive

logger = logging.getLogger(__name__)

class SnapshotQueueManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SnapshotQueueManager, cls).__new__(cls)
                cls._instance._init_queue()
            return cls._instance

    def _init_queue(self):
        self._queue = queue.Queue()
        self._workers = []
        # RTX 3080Ti의 넘치는 성능을 활용한 4개 병렬 워커 활성화
        for i in range(4):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"SnapshotWorkerThread-{i+1}")
            t.start()
            self._workers.append(t)
        logger.info("📸 하드웨어 가속 스냅샷 파이프라인이 활성화되었습니다 (4병렬).")

    def push_job(self, video_path: Path | str, output_dir: Path | str, product_code: str = "Unknown"):
        """스냅샷 추출 작업을 대기열에 넣습니다. (Non-blocking)"""
        job = {
            "video_path": Path(video_path),
            "output_dir": Path(output_dir),
            "product_code": product_code
        }
        self._queue.put(job)
        logger.info(f"📥 스냅샷 작업 접수: {product_code}. (대기: {self._queue.qsize()}개)")

    def _worker_loop(self):
        while True:
            job = self._queue.get()
            try:
                code = job["product_code"]
                vp = job["video_path"]
                od = job["output_dir"]
                
                logger.info(f"🚀 [Snapshot-Queue] 추출 시작: {code}")
                # extract_snapshots_auto_adaptive 내부에서 자동으로 CUDA 가속 사용 시도함
                extract_snapshots_auto_adaptive(vp, od)
                logger.info(f"✅ [Snapshot-Queue] 추출 완료: {code}")
            except Exception as e:
                logger.exception(f"❌ [Snapshot-Queue] 에러 발생: {e}")
            finally:
                self._queue.task_done()

# 전역 싱글턴 객체
snapshot_queue_manager = SnapshotQueueManager()
