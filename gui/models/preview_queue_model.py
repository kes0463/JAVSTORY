"""프리뷰(WebP) 생성 전역 큐 모델 (동시 실행 제한)."""

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
    output_path: str
    status: str  # queued|running|done|error
    progress: int
    message: str
    created_at_ms: int


class PreviewQueueListModel(QAbstractListModel):
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

        count = 0
        for i in sorted(to_del, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            self._items.pop(i)
            self.endRemoveRows()
            count += 1
        return count


class PreviewQueueController(QObject):
    _instance = None

    @staticmethod
    def instance() -> "PreviewQueueController | None":
        return PreviewQueueController._instance

    queueCountChanged = Signal()
    runningCountChanged = Signal()
    pendingCountChanged = Signal()
    toastMessage = Signal(str, str)  # msg, level
    logMessage = Signal(str)
    queueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        PreviewQueueController._instance = self
        self._model = PreviewQueueListModel(self)
        self._running: Dict[str, object] = {}  # job_id -> worker
        raw = (os.environ.get("JAVSTORY_PREVIEW_QUEUE_CONCURRENCY", "") or "").strip()
        try:
            n = int(raw) if raw else 2
        except ValueError:
            n = 2
        self._max_parallel = max(1, min(6, n))
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

        prev = self._model._find_latest_for_product(pc)
        if prev and prev.status in {"queued", "running"}:
            self.toastMessage.emit(f"[프리뷰] 이미 대기/진행 중입니다: {pc}", "info")
            self.logMessage.emit(f"[PreviewQueue] skip duplicate: {pc}")
            return

        from javstory.config.app_config import E_MEDIA_ROOT

        output_path = str(Path(E_MEDIA_ROOT) / pc / "Preview" / "preview.webp")
        outp = Path(output_path)
        if outp.is_file():
            try:
                from javstory.utils.derived_cache import is_up_to_date

                meta_path = outp.with_suffix(outp.suffix + ".meta.json")
                if is_up_to_date(
                    meta_path=meta_path,
                    inputs={"video": Path(vp)},
                    params={"duration_sec": 8.0},
                ):
                    self.toastMessage.emit(f"[프리뷰] 이미 최신입니다: {pc}", "info")
                    return
            except Exception:
                # 메타가 없거나 읽기 실패면 기존 동작(존재 스킵) 대신 재생성 기회를 준다.
                pass

        job_id = f"{pc}_{int(time.time() * 1000)}"
        job = _Job(
            job_id=job_id,
            product_code=pc,
            video_path=vp,
            output_path=output_path,
            status="queued",
            progress=0,
            message="대기 중",
            created_at_ms=int(time.time() * 1000),
        )
        self._model._append(job)
        self._emit_counts()
        self.toastMessage.emit(f"[프리뷰] 큐에 추가됨: {pc}", "success")
        self.logMessage.emit(f"[PreviewQueue] enqueued: {pc} | {os.path.basename(vp)}")
        self._pump()

    @Slot(str, str)
    def regenerate(self, product_code: str, video_path: str) -> None:
        """preview.webp가 있어도 강제로 삭제 후 재생성 큐 등록."""
        pc = (product_code or "").strip().upper()
        vp = (video_path or "").strip()
        if not pc or not vp:
            return

        prev = self._model._find_latest_for_product(pc)
        if prev and prev.status in {"queued", "running"}:
            self.toastMessage.emit(f"[프리뷰] 이미 대기/진행 중입니다: {pc}", "info")
            self.logMessage.emit(f"[PreviewQueue] skip duplicate(force): {pc}")
            return

        from javstory.config.app_config import E_MEDIA_ROOT

        output_path = Path(E_MEDIA_ROOT) / pc / "Preview" / "preview.webp"
        try:
            if output_path.is_file():
                output_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except TypeError:
            # py<3.8 compatibility guard (실제로는 3.12이지만 안전)
            try:
                if output_path.is_file():
                    output_path.unlink()
            except Exception:
                pass
        except Exception:
            pass

        # 강제 재생성은 enqueue 로직의 "exists" 체크를 우회해야 하므로 직접 job 생성
        job_id = f"{pc}_{int(time.time() * 1000)}"
        job = _Job(
            job_id=job_id,
            product_code=pc,
            video_path=vp,
            output_path=str(output_path),
            status="queued",
            progress=0,
            message="대기 중(재생성)",
            created_at_ms=int(time.time() * 1000),
        )
        self._model._append(job)
        self._emit_counts()
        self.toastMessage.emit(f"[프리뷰] 재생성 큐에 추가됨: {pc}", "success")
        self.logMessage.emit(f"[PreviewQueue] enqueued(force): {pc} | {os.path.basename(vp)}")
        self._pump()

    @Slot()
    def enqueueMissingPreviews(self) -> None:
        """DB를 스캔해 preview.webp 누락 작품만 큐 등록."""
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata
            from gui.library_data import guess_video_path_for_product_debug

            from javstory.config.app_config import E_MEDIA_ROOT

            session = get_db_session()
            try:
                rows = session.query(JAVMetadata.product_code, JAVMetadata.folder_path).all()
            finally:
                try:
                    session.close()
                except Exception:
                    pass

            added = 0
            skipped_no_video = 0
            skipped_exists = 0
            no_video_items: list[dict] = []
            for pc_raw, folder_path in (rows or []):
                pc = (pc_raw or "").strip().upper()
                if not pc:
                    continue
                outp = Path(E_MEDIA_ROOT) / pc / "Preview" / "preview.webp"
                if outp.is_file():
                    skipped_exists += 1
                    continue

                vp, searched_dirs, matched = guess_video_path_for_product_debug(pc, folder_path or None)
                if not vp or not vp.is_file():
                    skipped_no_video += 1
                    no_video_items.append(
                        {
                            "pc": pc,
                            "folder_path": (folder_path or "").strip(),
                            "searched_dirs": searched_dirs,
                            "matched_videos": matched,
                        }
                    )
                    continue
                self.enqueue(pc, str(vp))
                added += 1

            if no_video_items:
                # 로그에 상세를 남기고, 토스트는 요약만 출력
                for it in no_video_items[:200]:
                    fp = it.get("folder_path") or ""
                    sd = it.get("searched_dirs") or []
                    mv = it.get("matched_videos") or []
                    self.logMessage.emit(
                        "[프리뷰 백필] 영상 없음: "
                        f"{it.get('pc')} | folder_path={fp or '(없음)'} | "
                        f"searched={len(sd)} | matched={len(mv)}"
                    )
                    if sd:
                        self.logMessage.emit(f"  - searched_dirs: {sd}")
                    if mv:
                        self.logMessage.emit(f"  - matched_videos: {mv}")

            self.toastMessage.emit(
                f"[프리뷰 백필] 추가 {added}건 (존재 {skipped_exists} / 영상없음 {skipped_no_video})"
                + (
                    f" — 예: {', '.join(x.get('pc') for x in no_video_items[:5] if x.get('pc'))}"
                    if no_video_items
                    else ""
                ),
                "success" if added > 0 else "info",
            )
        except Exception as e:
            self.toastMessage.emit(f"[프리뷰 백필] 실패: {e}", "error")

    @Slot()
    def enqueueAllPreviewsForce(self) -> None:
        """DB를 스캔해 가능한 모든 작품을 프리뷰 '강제 재생성'으로 큐 등록."""
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata
            from gui.library_data import guess_video_path_for_product_debug

            session = get_db_session()
            try:
                rows = session.query(JAVMetadata.product_code, JAVMetadata.folder_path).all()
            finally:
                try:
                    session.close()
                except Exception:
                    pass

            added = 0
            skipped_no_video = 0
            no_video_items: list[dict] = []
            for pc_raw, folder_path in (rows or []):
                pc = (pc_raw or "").strip().upper()
                if not pc:
                    continue
                vp, searched_dirs, matched = guess_video_path_for_product_debug(pc, folder_path or None)
                if not vp or not vp.is_file():
                    skipped_no_video += 1
                    no_video_items.append(
                        {
                            "pc": pc,
                            "folder_path": (folder_path or "").strip(),
                            "searched_dirs": searched_dirs,
                            "matched_videos": matched,
                        }
                    )
                    continue
                self.regenerate(pc, str(vp))
                added += 1

            if no_video_items:
                for it in no_video_items[:200]:
                    fp = it.get("folder_path") or ""
                    sd = it.get("searched_dirs") or []
                    mv = it.get("matched_videos") or []
                    self.logMessage.emit(
                        "[프리뷰 일괄 재생성] 영상 없음: "
                        f"{it.get('pc')} | folder_path={fp or '(없음)'} | "
                        f"searched={len(sd)} | matched={len(mv)}"
                    )
                    if sd:
                        self.logMessage.emit(f"  - searched_dirs: {sd}")
                    if mv:
                        self.logMessage.emit(f"  - matched_videos: {mv}")

            self.toastMessage.emit(
                f"[프리뷰 일괄 재생성] 추가 {added}건 (영상없음 {skipped_no_video})"
                + (
                    f" — 예: {', '.join(x.get('pc') for x in no_video_items[:5] if x.get('pc'))}"
                    if no_video_items
                    else ""
                ),
                "success" if added > 0 else "info",
            )
        except Exception as e:
            self.toastMessage.emit(f"[프리뷰 일괄 재생성] 실패: {e}", "error")

    def _pump(self) -> None:
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
            from gui.workers.preview_worker import PreviewWorker
        except Exception as e:
            self._model._update_by_id(job.job_id, status="error", message=f"워커 로드 실패: {e}")
            self._emit_counts()
            return

        self._model._update_by_id(job.job_id, status="running", progress=0, message="시작 중...")
        self._emit_counts()

        worker = PreviewWorker(job.product_code, job.video_path, job.output_path)
        self._running[job.job_id] = worker
        self._last_progress_log[job.job_id] = -1

        worker.progressUpdated.connect(lambda p, jid=job.job_id: self._on_progress(jid, p))
        worker.resultReady.connect(lambda ok, msg, jid=job.job_id: self._on_result(jid, ok, msg))
        # worker는 스레드 종료(QThread.finished)까지 유지해야 안전함
        worker.finished.connect(lambda jid=job.job_id: self._on_thread_finished(jid))
        worker.start()
        self.logMessage.emit(f"[PreviewQueue] started: {job.product_code}")
        self._emit_counts()

    def _on_progress(self, job_id: str, percent: int) -> None:
        p = int(max(0, min(100, percent)))
        self._model._update_by_id(job_id, progress=p, message=f"{p}%")
        last = self._last_progress_log.get(job_id, -1)
        step = int(p // 10)
        if step != last and p < 100:
            self._last_progress_log[job_id] = step
            self.logMessage.emit(f"[PreviewQueue] progress: {p}% (job={job_id})")

    def _on_result(self, job_id: str, success: bool, message: str) -> None:
        if success:
            self._model._update_by_id(job_id, status="done", progress=100, message=message or "완료")
            self.logMessage.emit(f"[PreviewQueue] done: job={job_id} | {message}")
        else:
            self._model._update_by_id(job_id, status="error", message=message or "실패")
            self.logMessage.emit(f"[PreviewQueue] error: job={job_id} | {message}")
        self._emit_counts()

    @Slot(str)
    def removeJob(self, job_id: str) -> None:
        """프리뷰 생성 작업 삭제."""
        worker = self._running.pop(job_id, None)
        if worker:
            try:
                worker.terminate()
                worker.wait()
            except Exception:
                pass
            self.logMessage.emit(f"[PreviewQueue] terminated worker: job={job_id}")

        if self._model._remove_by_id(job_id):
            self.logMessage.emit(f"[PreviewQueue] removed job: {job_id}")
            self._emit_counts()
            self._pump()

    @Slot()
    def clearFinished(self) -> None:
        """완료/에러 항목 일괄 제거."""
        count = self._model._clear_finished()
        if count > 0:
            self.logMessage.emit(f"[PreviewQueue] cleared {count} finished jobs")
            self._emit_counts()

    def _on_thread_finished(self, job_id: str) -> None:
        self._running.pop(job_id, None)
        self._last_progress_log.pop(job_id, None)
        self._emit_counts()
        self._pump()

