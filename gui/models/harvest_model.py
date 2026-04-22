"""수집(Harvest) 모델: 크롤링 태스크 관리 + HarvestWorker 통합."""

from __future__ import annotations

from collections import deque
import os
import re
import time
from pathlib import Path

from PySide6.QtCore import (
    QObject, Property, Signal, Slot,
    QAbstractListModel, QModelIndex, Qt,
)


class HarvestTaskListModel(QAbstractListModel):
    SkuRole = Qt.ItemDataRole.UserRole + 1
    StatusRole = Qt.ItemDataRole.UserRole + 2
    ProgressRole = Qt.ItemDataRole.UserRole + 3
    MessageRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

    def roleNames(self):
        return {
            self.SkuRole: b"sku",
            self.StatusRole: b"status",
            self.ProgressRole: b"progress",
            self.MessageRole: b"message",
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        mapping = {
            self.SkuRole: "sku",
            self.StatusRole: "status",
            self.ProgressRole: "progress",
            self.MessageRole: "message",
        }
        return item.get(mapping.get(role))

    def _find_row(self, sku: str) -> int:
        for i, it in enumerate(self._items):
            if it["sku"] == sku:
                return i
        return -1

    def upsert(self, sku: str, status: str, progress: int, message: str):
        row = self._find_row(sku)
        if row < 0:
            self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
            self._items.append({"sku": sku, "status": status, "progress": progress, "message": message})
            self.endInsertRows()
        else:
            self._items[row].update({"status": status, "progress": progress, "message": message})
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx)

    def remove(self, sku: str):
        row = self._find_row(sku)
        if row >= 0:
            self.beginRemoveRows(QModelIndex(), row, row)
            self._items.pop(row)
            self.endRemoveRows()


class HarvestModel(QObject):
    grokEnabledChanged = Signal()
    taskCountChanged = Signal()
    queuedCountChanged = Signal()
    finishedCountChanged = Signal()
    logMessage = Signal(str)
    toastMessage = Signal(str, str)  # message, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grok_enabled = os.environ.get(
            "JAVSTORY_STORY_ANALYSIS_ENABLED", "1"
        ).strip().lower() in ("1", "true", "yes", "on")
        self._tasks = HarvestTaskListModel(self)
        self._workers: dict[str, object] = {}
        self._active_refs: list[object] = []
        # 전역 Harvest 실행 큐(품번 단일 추가까지 포함)
        self._global_queue: deque = deque()
        # 배치(폴더/상위폴더) 병렬 실행용 큐/상태
        self._batch_queues: dict[str, deque] = {}
        self._batch_active_counts: dict[str, int] = {}
        # 폴더 수집 큐(사용자 시작 트리거)
        self._queued_entries: list[tuple] = []

    @Property(QObject, constant=True)
    def tasks(self):
        return self._tasks

    @Property(bool, notify=grokEnabledChanged)
    def grokEnabled(self):
        return self._grok_enabled

    @grokEnabled.setter  # type: ignore[attr-defined]
    def grokEnabled(self, val: bool):
        if val != self._grok_enabled:
            self._grok_enabled = val
            os.environ["JAVSTORY_STORY_ANALYSIS_ENABLED"] = "1" if val else "0"
            self.grokEnabledChanged.emit()

    @Property(int, notify=queuedCountChanged)
    def queuedCount(self) -> int:
        return len(self._queued_entries)

    @Property(int, notify=finishedCountChanged)
    def finishedCount(self) -> int:
        return sum(
            1 for it in self._tasks._items
            if it.get("status") in ("done", "error")
        )

    # ── Slots (QML에서 호출) ──────────────────────────

    @Slot(str)
    def addTask(self, query: str):
        """품번(쉼표·공백 구분) 추가."""
        skus = re.split(r"[,\s;\n]+", query)
        clean = list(dict.fromkeys(s.strip().upper() for s in skus if s.strip()))
        entries = [(sku, False, None, False) for sku in clean if sku]
        if not entries:
            return
        self._enqueue_global(entries)
        self._pump_global()

    @Slot("QStringList", bool)
    def recrawlProducts(self, product_codes: list[str], force: bool = True) -> None:
        """
        라이브러리 등에서 선택한 품번들을 재크롤링(강제)한다.
        - product_codes: ["STAR-471", ...]
        - force=True면 DB가 완비되어도 다시 웹 수집/번역을 수행하도록 워커에 전달
        """
        pcs = []
        try:
            for pc in (product_codes or []):
                s = str(pc or "").strip().upper()
                if s:
                    pcs.append(s)
        except Exception:
            pcs = []
        if not pcs:
            return
        entries = [(pc, False, None, bool(force)) for pc in pcs]
        self._enqueue_global(entries)
        self._pump_global()
        self.toastMessage.emit(f"[재크롤링] {len(entries)}건 큐에 추가됨", "success")

    @Slot(str)
    def addFolder(self, path: str):
        """단일 폴더 수집."""
        from javstory.harvest.folder_harvest import plan_single_folder, planned_to_worker_entries
        jobs, warns = plan_single_folder(Path(path))
        for w in warns:
            self.logMessage.emit(f"[경고] {w}")
        if not jobs:
            self.toastMessage.emit("실행할 작업이 없습니다.", "warning")
            return
        entries = planned_to_worker_entries(jobs)
        self._enqueue_global(entries)
        self._pump_global()
        self.toastMessage.emit(f"{len(jobs)}건 수집 시작", "success")

    @Slot(str)
    def addParentFolder(self, path: str):
        """상위 폴더 (하위 일괄) 수집."""
        from javstory.harvest.folder_harvest import plan_parent_folder, planned_to_worker_entries
        jobs, warns = plan_parent_folder(Path(path))
        for w in warns:
            self.logMessage.emit(f"[경고] {w}")
        if not jobs:
            self.toastMessage.emit("실행할 작업이 없습니다.", "warning")
            return
        entries = planned_to_worker_entries(jobs)
        self._enqueue_global(entries)
        self._pump_global()
        self.toastMessage.emit(f"{len(jobs)}건 하위 폴더 수집 시작", "success")

    @Slot(str)
    def queueFolder(self, path: str):
        """단일 폴더 수집: 즉시 실행하지 않고 큐에 추가."""
        from javstory.harvest.folder_harvest import plan_single_folder, planned_to_worker_entries
        jobs, warns = plan_single_folder(Path(path))
        for w in warns:
            self.logMessage.emit(f"[경고] {w}")
        if not jobs:
            self.toastMessage.emit("큐에 추가할 작업이 없습니다.", "warning")
            return
        entries = planned_to_worker_entries(jobs)
        self._queued_entries.extend(entries)
        for e in entries:
            sku = self._entry_sku(e)
            if sku:
                self._tasks.upsert(sku, "waiting", 0, "큐 대기")
        self.queuedCountChanged.emit()
        self.toastMessage.emit(f"{len(jobs)}건 큐에 추가됨 (총 {len(self._queued_entries)}건)", "success")

    @Slot(str)
    def queueParentFolder(self, path: str):
        """상위 폴더(하위 일괄) 수집: 즉시 실행하지 않고 큐에 추가."""
        from javstory.harvest.folder_harvest import plan_parent_folder, planned_to_worker_entries
        jobs, warns = plan_parent_folder(Path(path))
        for w in warns:
            self.logMessage.emit(f"[경고] {w}")
        if not jobs:
            self.toastMessage.emit("큐에 추가할 작업이 없습니다.", "warning")
            return
        entries = planned_to_worker_entries(jobs)
        self._queued_entries.extend(entries)
        for e in entries:
            sku = self._entry_sku(e)
            if sku:
                self._tasks.upsert(sku, "waiting", 0, "큐 대기")
        self.queuedCountChanged.emit()
        self.toastMessage.emit(f"{len(jobs)}건 큐에 추가됨 (총 {len(self._queued_entries)}건)", "success")

    @Slot("QStringList")
    def queueFolders(self, paths: list[str]):
        """여러 개별 폴더를 일괄적으로 수집 큐에 추가."""
        if not paths:
            return
        from javstory.harvest.folder_harvest import plan_folder_paths, planned_to_worker_entries
        path_objs = [Path(p) for p in paths if p]
        if not path_objs:
            return
            
        jobs, warns = plan_folder_paths(path_objs)
        for w in warns:
            self.logMessage.emit(f"[경고] {w}")
            
        if not jobs:
            self.toastMessage.emit("큐에 추가할 작업이 없습니다.", "warning")
            return
            
        entries = planned_to_worker_entries(jobs)
        self._queued_entries.extend(entries)
        for e in entries:
            sku = self._entry_sku(e)
            if sku:
                self._tasks.upsert(sku, "waiting", 0, "큐 대기")
        
        self.queuedCountChanged.emit()
        self.toastMessage.emit(f"{len(jobs)}건 큐에 성공적으로 추가됨", "success")

    @Slot()
    def clearQueued(self):
        """큐 비우기(실행 전 대기 항목만)."""
        if not self._queued_entries:
            return
        # 큐 대기 상태인 항목은 화면에서 제거하지 않고 waiting 메시지만 되돌림(보수적)
        self._queued_entries = []
        self.queuedCountChanged.emit()
        self.toastMessage.emit("수집 큐를 비웠습니다.", "info")

    @Slot()
    def startQueued(self):
        """큐에 쌓인 폴더 수집 작업을 실행."""
        if not self._queued_entries:
            self.toastMessage.emit("수집 큐가 비어 있습니다.", "warning")
            return
        entries = list(self._queued_entries)
        self._queued_entries = []
        self.queuedCountChanged.emit()
        self._enqueue_global(entries)
        self._pump_global()
        self.toastMessage.emit(f"{len(entries)}건 수집 시작 (큐)", "success")

    @Slot(str)
    def removeTask(self, sku: str):
        if sku in self._workers:
            w = self._workers.pop(sku)
            w.stop()
        self._tasks.remove(sku)
        # 전역 실행 큐에서도 제거
        self._remove_from_global_queue(sku)
        # 배치 큐에 남아있는 항목도 제거
        self._remove_from_batch_queues(sku)
        # 실행 전 큐에서도 제거
        self._remove_from_queued_entries(sku)
        self.finishedCountChanged.emit()

    @Slot()
    def removeFinished(self):
        """완료(done) 또는 실패(error) 상태의 모든 태스크를 제거."""
        finished = [
            it["sku"] for it in list(self._tasks._items)
            if it.get("status") in ("done", "error")
        ]
        if not finished:
            return
        for sku in finished:
            self._tasks.remove(sku)
        self.finishedCountChanged.emit()
        self.toastMessage.emit(f"{len(finished)}건 완료 항목 제거", "info")

    # ── 내부 ─────────────────────────────────────────

    def _enqueue_global(self, entries: list[tuple[str, bool, str | None]]) -> None:
        """전역 큐에 엔트리를 적재하고 UI에 waiting 상태로 노출."""
        for e in entries or []:
            sku = self._entry_sku(e)
            if sku:
                self._tasks.upsert(sku, "waiting", 0, "대기 중...")
            self._global_queue.append(e)
        self.taskCountChanged.emit()

    def _launch_worker(self, key: str, entries):
        from gui.workers.harvest_worker import HarvestWorker

        if key in self._workers:
            old = self._workers.pop(key)
            old.stop()
            old.wait()

        # entries가 여러 개인 배치면 병렬 큐 실행(추천 A)
        if isinstance(entries, (list, tuple)) and len(entries) > 1:
            self._launch_batch(key, list(entries))
            return

        worker = HarvestWorker(entries, grok_enabled=self._grok_enabled, parent=self)
        worker._harvest_key = key  # type: ignore[attr-defined]
        worker.progress.connect(self._on_progress)
        worker.task_finished.connect(self._on_finished)
        worker.finished.connect(lambda: self._on_thread_done(worker))

        self._workers[key] = worker
        self._active_refs.append(worker)
        worker.start()

    def _pump_global(self) -> None:
        """전역 큐에서 동시 실행 수만큼 워커를 채운다."""
        conc = self._harvest_concurrency()
        # 현재 실행중인 워커 수 기준으로 빈 슬롯만큼만 시작
        while len(self._workers) < conc and self._global_queue:
            entry = self._global_queue.popleft()
            if not entry:
                continue
            sku = self._entry_sku(entry)
            if not sku:
                continue
            # 이미 실행 중이면 큐 뒤로 보내고 다음으로
            if sku in self._workers:
                self._global_queue.append(entry)
                # 모든 항목이 실행중 sku로만 채워진 경우 무한루프 방지
                break
            self._launch_worker(sku, [entry])

    def _harvest_concurrency(self) -> int:
        raw = (os.environ.get("JAVSTORY_HARVEST_CONCURRENCY", "") or "").strip()
        if raw:
            try:
                n = int(raw)
            except ValueError:
                n = 2
        else:
            n = 2
        # 안정성: 1..5로 제한
        return max(1, min(5, n))

    def _remove_from_global_queue(self, sku: str) -> None:
        s = (sku or "").strip().upper()
        if not s or not self._global_queue:
            return
        try:
            items = [e for e in list(self._global_queue) if self._entry_sku(e) != s]
            self._global_queue = deque(items)
        except Exception:
            pass

    def _entry_sku(self, entry) -> str:
        """(target,is_path,pc_override,...) → UI 키(sku) 추정."""
        try:
            target = entry[0]
            is_path_flag = bool(entry[1])
            pc_override = entry[2] if len(entry) >= 3 else None
        except Exception:
            return str(entry).strip().upper()
        pc = (pc_override or "").strip().upper()
        if pc:
            return pc
        if bool(is_path_flag):
            try:
                return Path(str(target)).stem.upper()
            except Exception:
                return str(target).strip().upper()
        return str(target).strip().upper()

    def _remove_from_batch_queues(self, sku: str) -> None:
        s = (sku or "").strip().upper()
        if not s:
            return
        for bk, q in list(self._batch_queues.items()):
            try:
                items = [e for e in q if self._entry_sku(e) != s]
                self._batch_queues[bk] = deque(items)
            except Exception:
                continue

    def _remove_from_queued_entries(self, sku: str) -> None:
        s = (sku or "").strip().upper()
        if not s or not self._queued_entries:
            return
        before = len(self._queued_entries)
        self._queued_entries = [e for e in self._queued_entries if self._entry_sku(e) != s]
        if len(self._queued_entries) != before:
            self.queuedCountChanged.emit()

    def _launch_batch(self, batch_key: str, entries: list[tuple[str, bool, str | None]]) -> None:
        """
        배치 entries를 병렬 워커 여러 개로 분산 실행한다.
        - 동시 실행: JAVSTORY_HARVEST_CONCURRENCY (기본 3, 최대 5)
        - 각 워커는 엔트리 1개만 처리(완료 시 다음 엔트리를 새 워커로 시작)
        """
        # 기존 배치가 있으면 덮어쓰기(큐 교체)
        q = deque(entries)
        self._batch_queues[batch_key] = q
        self._batch_active_counts[batch_key] = 0

        # 큐에 있는 항목을 UI에 미리 노출(대기)
        for e in entries:
            sku = self._entry_sku(e)
            if sku:
                self._tasks.upsert(sku, "waiting", 0, "대기 중...")

        conc = self._harvest_concurrency()
        for _ in range(conc):
            self._maybe_start_next_in_batch(batch_key)

    def _maybe_start_next_in_batch(self, batch_key: str) -> None:
        from gui.workers.harvest_worker import HarvestWorker

        q = self._batch_queues.get(batch_key)
        if not q:
            return
        entry = q.popleft() if q else None
        if not entry:
            return

        sku = self._entry_sku(entry)
        # 동일 sku가 이미 실행중이면(드문 케이스) 다시 큐 끝으로
        if sku in self._workers:
            q.append(entry)
            return

        worker = HarvestWorker([entry], grok_enabled=self._grok_enabled, parent=self)
        worker._harvest_key = sku  # type: ignore[attr-defined]
        worker._batch_key = batch_key  # type: ignore[attr-defined]
        worker.progress.connect(self._on_progress)
        worker.task_finished.connect(self._on_finished)
        worker.finished.connect(lambda: self._on_thread_done(worker))

        self._workers[sku] = worker
        self._active_refs.append(worker)
        self._batch_active_counts[batch_key] = self._batch_active_counts.get(batch_key, 0) + 1
        worker.start()

    def _on_progress(self, sku: str, message: str, percentage: int):
        self._tasks.upsert(sku, "running", percentage, message)
        self.logMessage.emit(f"[{sku}] {message}")

    def _on_finished(self, sku: str, success: bool, message: str):
        status = "done" if success else "error"
        self._tasks.upsert(sku, status, 100 if success else 0, message)
        self.logMessage.emit(f"[{sku}] {'성공' if success else '실패'}: {message}")
        self.finishedCountChanged.emit()

    def _on_thread_done(self, worker):
        if worker in self._active_refs:
            self._active_refs.remove(worker)
        # 워커 키 제거
        key = getattr(worker, "_harvest_key", None)
        if key and key in self._workers and self._workers.get(key) is worker:
            self._workers.pop(key, None)
        else:
            for k, w in list(self._workers.items()):
                if w is worker:
                    self._workers.pop(k, None)
                    key = k
                    break

        # 다음 작업 시작(전역 큐)
        self._pump_global()
        worker.deleteLater()
