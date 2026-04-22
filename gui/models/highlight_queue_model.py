"""하이라이트 생성 전역 큐 모델 (동시 실행 2개 제한)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import (
    QObject,
    Property,
    Signal,
    Slot,
    QAbstractListModel,
    QModelIndex,
    Qt,
)


@dataclass
class _Job:
    job_id: str
    product_code: str
    video_path: str
    output_dir: str
    status: str  # queued|running|done|error
    progress: int
    message: str
    created_at_ms: int


class HighlightQueueListModel(QAbstractListModel):
    JobIdRole = Qt.ItemDataRole.UserRole + 1
    ProductCodeRole = Qt.ItemDataRole.UserRole + 2
    VideoNameRole = Qt.ItemDataRole.UserRole + 3
    StatusRole = Qt.ItemDataRole.UserRole + 4
    ProgressRole = Qt.ItemDataRole.UserRole + 5
    MessageRole = Qt.ItemDataRole.UserRole + 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[_Job] = []

    def roleNames(self):
        return {
            self.JobIdRole: b"jobId",
            self.ProductCodeRole: b"productCode",
            self.VideoNameRole: b"videoName",
            self.StatusRole: b"status",
            self.ProgressRole: b"progress",
            self.MessageRole: b"message",
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        it = self._items[index.row()]
        if role == self.JobIdRole:
            return it.job_id
        if role == self.ProductCodeRole:
            return it.product_code
        if role == self.VideoNameRole:
            return os.path.basename(it.video_path)
        if role == self.StatusRole:
            return it.status
        if role == self.ProgressRole:
            return int(it.progress)
        if role == self.MessageRole:
            return it.message
        return None

    def _append(self, job: _Job) -> None:
        start = len(self._items)
        self.beginInsertRows(QModelIndex(), start, start)
        self._items.append(job)
        self.endInsertRows()

    def _update_by_id(self, job_id: str, **kwargs) -> None:
        for i, it in enumerate(self._items):
            if it.job_id == job_id:
                for k, v in kwargs.items():
                    if hasattr(it, k):
                        setattr(it, k, v)
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx)
                return

    def _find_latest_for_product(self, product_code: str) -> Optional[_Job]:
        pc = (product_code or "").strip().upper()
        for it in reversed(self._items):
            if (it.product_code or "").strip().upper() == pc:
                return it
        return None

    def _all(self) -> list[_Job]:
        return list(self._items)

    def _remove_by_id(self, job_id: str) -> bool:
        for i, it in enumerate(self._items):
            if it.job_id == job_id:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._items.pop(i)
                self.endRemoveRows()
                return True
        return False

    def _clear_finished(self) -> int:
        to_del = []
        for i, it in enumerate(self._items):
            if it.status in {"done", "error"}:
                to_del.append(i)

        if not to_del:
            return 0

        # 역순으로 제거해야 인덱스가 꼬이지 않음
        count = 0
        for i in sorted(to_del, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            self._items.pop(i)
            self.endRemoveRows()
            count += 1
        return count


class HighlightQueueController(QObject):
    _instance = None

    @staticmethod
    def instance() -> "HighlightQueueController | None":
        return HighlightQueueController._instance

    queueCountChanged = Signal()
    runningCountChanged = Signal()
    pendingCountChanged = Signal()
    toastMessage = Signal(str, str)  # msg, level
    logMessage = Signal(str)
    queueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        HighlightQueueController._instance = self
        self._model = HighlightQueueListModel(self)
        self._running: Dict[str, object] = {}  # job_id -> worker
        raw = (os.environ.get("JAVSTORY_HIGHLIGHT_QUEUE_CONCURRENCY", "") or "").strip()
        try:
            n = int(raw) if raw else 2
        except ValueError:
            n = 2
        self._max_parallel = max(1, min(4, n))
        self._last_progress_log: Dict[str, int] = {}

    @Property(QObject, constant=True)
    def queue(self):
        return self._model

    @Property(int, notify=queueCountChanged)
    def queueCount(self) -> int:
        return self._model.rowCount()

    @Property(int, notify=runningCountChanged)
    def runningCount(self) -> int:
        return len(self._running)

    @Property(int, notify=pendingCountChanged)
    def pendingCount(self) -> int:
        n = 0
        for it in self._model._all():
            if it.status in {"queued", "running"}:
                n += 1
        return n

    def _emit_counts(self) -> None:
        self.queueCountChanged.emit()
        self.runningCountChanged.emit()
        self.pendingCountChanged.emit()
        self.queueChanged.emit()

    @Slot(str, result="QVariantMap")
    def productState(self, product_code: str):
        """특정 품번의 최신 하이라이트 작업 상태를 반환 (QML용)."""
        pc = (product_code or "").strip().upper()
        if not pc:
            return {"status": "none", "progress": 0, "message": ""}
        it = self._model._find_latest_for_product(pc)
        if not it:
            return {"status": "none", "progress": 0, "message": ""}
        return {
            "status": it.status,
            "progress": int(it.progress or 0),
            "message": it.message or "",
        }

    @Slot(str, str)
    def enqueue(self, product_code: str, video_path: str) -> None:
        pc = (product_code or "").strip().upper()
        vp = (video_path or "").strip()
        if not pc or not vp:
            return

        # 이미 queued/running인 동일 품번은 중복 등록 방지
        prev = self._model._find_latest_for_product(pc)
        if prev and prev.status in {"queued", "running"}:
            self.toastMessage.emit(f"[하이라이트] 이미 대기/진행 중입니다: {pc}", "info")
            self.logMessage.emit(f"[HighlightQueue] skip duplicate: {pc}")
            return

        from javstory.config.app_config import E_MEDIA_ROOT
        output_dir = str(Path(E_MEDIA_ROOT) / pc / "Highlight")
        job_id = f"{pc}_{int(time.time() * 1000)}"
        job = _Job(
            job_id=job_id,
            product_code=pc,
            video_path=vp,
            output_dir=output_dir,
            status="queued",
            progress=0,
            message="대기 중",
            created_at_ms=int(time.time() * 1000),
        )
        self._model._append(job)
        self._emit_counts()
        self.toastMessage.emit(f"[하이라이트] 큐에 추가됨: {pc}", "success")
        self.logMessage.emit(f"[HighlightQueue] enqueued: {pc} | {os.path.basename(vp)}")
        self._pump()

    def _pump(self) -> None:
        # running 슬롯이 남아 있으면 queued job을 시작
        if len(self._running) >= self._max_parallel:
            return

        for it in self._model._all():
            if len(self._running) >= self._max_parallel:
                break
            if it.status != "queued":
                continue
            self._start_job(it)

    def _start_job(self, job: _Job) -> None:
        try:
            from gui.workers.highlight_worker import HighlightWorker
        except Exception as e:
            self._model._update_by_id(job.job_id, status="error", message=f"워커 로드 실패: {e}")
            self._emit_counts()
            return

        self._model._update_by_id(job.job_id, status="running", progress=0, message="시작 중...")
        self._emit_counts()

        worker = HighlightWorker(job.product_code, job.video_path, job.output_dir)
        self._running[job.job_id] = worker
        self._last_progress_log[job.job_id] = -1

        worker.progressUpdated.connect(lambda p, jid=job.job_id: self._on_progress(jid, p))
        worker.finished.connect(lambda ok, msg, jid=job.job_id: self._on_finished(jid, ok, msg))
        worker.start()
        self.logMessage.emit(f"[HighlightQueue] started: {job.product_code}")
        self._emit_counts()

    def _on_progress(self, job_id: str, percent: int) -> None:
        p = int(max(0, min(100, percent)))
        self._model._update_by_id(job_id, progress=p, message=f"{p}%")
        # 터미널 로그는 과도하므로 10% 단위로만 출력
        last = self._last_progress_log.get(job_id, -1)
        step = int(p // 10)
        if step != last and p < 100:
            self._last_progress_log[job_id] = step
            self.logMessage.emit(f"[HighlightQueue] progress: {p}% (job={job_id})")

    def _on_finished(self, job_id: str, success: bool, message: str) -> None:
        # job snapshot (UI 갱신용)
        job = None
        try:
            for it in self._model._all():
                if it.job_id == job_id:
                    job = it
                    break
        except Exception:
            job = None

        self._running.pop(job_id, None)
        self._last_progress_log.pop(job_id, None)
        if success:
            self._model._update_by_id(job_id, status="done", progress=100, message=message or "완료")
            self.logMessage.emit(f"[HighlightQueue] done: job={job_id} | {message}")
        else:
            # removeJob에 의해 중단된 경우 이미 목록에서 사라졌을 수 있음
            self._model._update_by_id(job_id, status="error", message=message or "실패")
            self.logMessage.emit(f"[HighlightQueue] error: job={job_id} | {message}")
        self._emit_counts()

        # 현재 상세 화면이 해당 품번이면 즉시 재로드하여 highlightPath 반영
        try:
            if success and job and (job.product_code or "").strip():
                from gui.models.library_model import LibraryModel
                lib = LibraryModel.instance()
                pc = (job.product_code or "").strip().upper()
                if lib and lib.detail and getattr(lib.detail, "productCode", "") == pc:
                    lib.loadDetail(pc)
        except Exception:
            pass

        self._pump()

    @Slot(str)
    def removeJob(self, job_id: str) -> None:
        """대기/진행/완료 작업을 즉시 삭제."""
        # 실행 중이면 워커 중단
        worker = self._running.pop(job_id, None)
        if worker:
            try:
                worker.terminate()
                worker.wait()
            except Exception:
                pass
            self.logMessage.emit(f"[HighlightQueue] terminated worker: job={job_id}")

        if self._model._remove_by_id(job_id):
            self.logMessage.emit(f"[HighlightQueue] removed job: {job_id}")
            self._emit_counts()
            # 실행 중인게 빠졌으니 다음 작업 펌핑
            self._pump()

    @Slot()
    def clearFinished(self) -> None:
        """완료 또는 에러 상태인 항목을 모두 제거."""
        count = self._model._clear_finished()
        if count > 0:
            self.logMessage.emit(f"[HighlightQueue] cleared {count} finished jobs")
            self._emit_counts()

