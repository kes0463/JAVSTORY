"""모자이크 제거(Mosaic Removal) 전역 큐 모델 (LADA-CLI 연동 대기)."""

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


class MosaicQueueListModel(QAbstractListModel):
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
        count = 0
        for i in sorted(to_del, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            self._items.pop(i)
            self.endRemoveRows()
            count += 1
        return count


class MosaicQueueController(QObject):
    _instance = None

    @staticmethod
    def instance() -> "MosaicQueueController | None":
        return MosaicQueueController._instance

    queueCountChanged = Signal()
    runningCountChanged = Signal()
    pendingCountChanged = Signal()
    toastMessage = Signal(str, str)
    logMessage = Signal(str)
    queueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        MosaicQueueController._instance = self
        self._model = MosaicQueueListModel(self)
        self._running: Dict[str, object] = {}
        self._max_parallel = 1  # 모자이크 제거는 GPU 부하가 크므로 1개 제한 권장

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
        for it in self._model._items:
            if it.status in {"queued", "running"}:
                n += 1
        return n

    def _emit_counts(self) -> None:
        self.queueCountChanged.emit()
        self.runningCountChanged.emit()
        self.pendingCountChanged.emit()
        self.queueChanged.emit()

    @Slot(str, str)
    def enqueue(self, product_code: str, video_path: str) -> None:
        pc = (product_code or "").strip().upper()
        vp = (video_path or "").strip()
        if not pc or not vp:
            return
        
        # 중복 체크 생략 (LADA 연동 시 보강)
        job_id = f"mopa_{pc}_{int(time.time() * 1000)}"
        job = _Job(
            job_id=job_id,
            product_code=pc,
            video_path=vp,
            output_dir="", # 추후 결정
            status="queued",
            progress=0,
            message="연동 대기 중",
            created_at_ms=int(time.time() * 1000),
        )
        self._model._append(job)
        self._emit_counts()
        self.toastMessage.emit(f"[모자이크 제거] 큐에 추가됨: {pc}", "info")

    @Slot(str)
    def removeJob(self, job_id: str) -> None:
        if self._model._remove_by_id(job_id):
            self._emit_counts()

    @Slot()
    def clearFinished(self) -> None:
        if self._model._clear_finished() > 0:
            self._emit_counts()
