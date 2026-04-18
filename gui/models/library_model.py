"""라이브러리 모델: 작품 목록/필터/정렬 + 상세 정보."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QObject, QTimer, Property, Signal, Slot,
    QAbstractListModel, QModelIndex, Qt,
)

from gui.models.detail_edit_draft import DetailEditDraft
from gui.models.scene_edit_model import SceneEditModel


class WorkListModel(QAbstractListModel):
    ProductCodeRole = Qt.ItemDataRole.UserRole + 1
    TitleKoRole = Qt.ItemDataRole.UserRole + 2
    TitleJaRole = Qt.ItemDataRole.UserRole + 3
    ActorsKoRole = Qt.ItemDataRole.UserRole + 4
    CoverPathRole = Qt.ItemDataRole.UserRole + 5
    SceneCountRole = Qt.ItemDataRole.UserRole + 6
    PipelineStageRole = Qt.ItemDataRole.UserRole + 7
    ReleaseDateRole = Qt.ItemDataRole.UserRole + 8
    HasCanonicalRole = Qt.ItemDataRole.UserRole + 9
    PartCountRole = Qt.ItemDataRole.UserRole + 10
    IsHardcodedRole = Qt.ItemDataRole.UserRole + 11
    HasJaSrtRole = Qt.ItemDataRole.UserRole + 12
    HasKoSrtRole = Qt.ItemDataRole.UserRole + 13
    LampHardcodedRole = Qt.ItemDataRole.UserRole + 14

    _ROLE_MAP = {
        ProductCodeRole: "product_code",
        TitleKoRole: "title_ko",
        TitleJaRole: "title_ja",
        ActorsKoRole: "actors_ko",
        CoverPathRole: "cover_path",
        SceneCountRole: "scene_count",
        PipelineStageRole: "pipeline_stage",
        ReleaseDateRole: "release_date",
        HasCanonicalRole: "has_canonical",
        PartCountRole: "part_count",
        IsHardcodedRole: "is_hardcoded",
        HasJaSrtRole: "has_ja_srt",
        HasKoSrtRole: "has_ko_srt",
        LampHardcodedRole: "lamp_hardcoded",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

    def roleNames(self):
        return {
            self.ProductCodeRole: b"productCode",
            self.TitleKoRole: b"titleKo",
            self.TitleJaRole: b"titleJa",
            self.ActorsKoRole: b"actorsKo",
            self.CoverPathRole: b"coverPath",
            self.SceneCountRole: b"sceneCount",
            self.PipelineStageRole: b"pipelineStage",
            self.ReleaseDateRole: b"releaseDate",
            self.HasCanonicalRole: b"hasCanonical",
            self.PartCountRole: b"partCount",
            self.IsHardcodedRole: b"isHardcoded",
            self.HasJaSrtRole: b"hasJaSrt",
            self.HasKoSrtRole: b"hasKoSrt",
            self.LampHardcodedRole: b"lampHardcoded",
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key = self._ROLE_MAP.get(role)
        if key:
            return self._items[index.row()].get(key)
        return None

    def refresh(self, items: list[dict]):
        self.beginResetModel()
        self._items = items
        self.endResetModel()


class LibraryDetailObject(QObject):
    """단일 작품 상세 정보를 QML에 노출."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict = {}

    def load(self, data: dict):
        self._data = data
        self.changed.emit()

    def _get(self, key, default=""):
        return self._data.get(key, default)

    @Property(str, notify=changed)
    def productCode(self): return self._get("product_code")
    @Property(str, notify=changed)
    def titleKo(self): return self._get("title_ko")
    @Property(str, notify=changed)
    def titleJa(self): return self._get("title_ja")
    @Property(str, notify=changed)
    def actorsKo(self): return self._get("actors_ko")
    @Property(str, notify=changed)
    def makerKo(self): return self._get("maker_ko")
    @Property(str, notify=changed)
    def releaseDate(self): return self._get("release_date")
    @Property(str, notify=changed)
    def synopsisKo(self): return self._get("synopsis_ko")
    @Property(str, notify=changed)
    def genresKo(self): return self._get("genres_ko")
    @Property(str, notify=changed)
    def coverPath(self): return self._get("cover_path")
    @Property(int, notify=changed)
    def sceneCount(self): return self._get("scene_count", 0)
    @Property(str, notify=changed)
    def pipelineStage(self): return self._get("pipeline_stage", "none")
    @Property(bool, notify=changed)
    def hasCanonical(self): return self._get("has_canonical", False)
    @Property(str, notify=changed)
    def overallSummary(self): return self._get("overall_summary", "")
    @Property(str, notify=changed)
    def grokJson(self): return self._get("grok_json", "")
    @Property(list, notify=changed)
    def stillPaths(self): return self._get("still_paths", [])
    @Property(str, notify=changed)
    def videoPath(self): return self._get("video_path", "")
    @Property(str, notify=changed)
    def grokScenesJson(self): return self._get("grok_scenes_json", "[]")
    @Property(bool, notify=changed)
    def isHardcoded(self): return self._get("is_hardcoded", False)
    @Property(bool, notify=changed)
    def hasJaSrt(self): return self._get("has_ja_srt", False)
    @Property(bool, notify=changed)
    def hasKoSrt(self): return self._get("has_ko_srt", False)
    @Property(bool, notify=changed)
    def lampHardcoded(self): return self._get("lamp_hardcoded", False)
    @Property(str, notify=changed)
    def folderPath(self): return self._get("folder_path", "")
    @Property(str, notify=changed)
    def digestPath(self): return self._get("digest_path", "")


class LibraryModel(QObject):
    _instance = None

    @staticmethod
    def instance() -> LibraryModel | None:
        return LibraryModel._instance

    # 검색 및 필터링 관련 시그널
    searchQueryChanged = Signal()
    sortModeChanged = Signal()
    workCountChanged = Signal()
    detailLoaded = Signal()
    summariesReloaded = Signal()  # DB 요약·연결 경로 갱신 시 (폴더 감시 목록 리프레시용)
    # 품번, 사라진 경로, 후보 경로 목록 — 폴더 이동 감시에서 사용자 확인 팝업용
    folderBindingNeedsReview = Signal(str, str, list)
    
    # 스냅샷 추출 관련 시그널
    snapshotProgress = Signal(int, int) # current, total
    snapshotFinished = Signal(bool, str) # success, message
    logMessage = Signal(str)
    toastMessage = Signal(str, str)
    requestFolderSelection = Signal(str)
    isGeneratingDigestChanged = Signal()
    digestProgressChanged = Signal()
    isExtractingSnapshotsChanged = Signal()
    snapshotProgressMsgChanged = Signal()
    detailEditingChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        LibraryModel._instance = self
        self._search_query = ""
        self._sort_mode = 0
        self._all_summaries: list = []
        self._works = WorkListModel(self)
        self._detail = LibraryDetailObject(self)
        self._snapshot_worker = None
        self._digest_worker = None
        self._is_generating_digest = False
        self._digest_progress = 0
        self._is_extracting_snapshots = False
        self._snapshot_progress_msg = ""
        self._detail_editing = False
        self._edit_draft = DetailEditDraft(self)
        self._scene_edit = SceneEditModel(self)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._rebuild)

    @Property(QObject, constant=True)
    def works(self): return self._works

    @Property(QObject, constant=True)
    def detail(self): return self._detail

    @Property(QObject, constant=True)
    def editDraft(self): return self._edit_draft

    @Property(QObject, constant=True)
    def sceneEdit(self): return self._scene_edit

    @Property(bool, notify=detailEditingChanged)
    def detailEditing(self) -> bool:
        return self._detail_editing

    @Property(str, notify=searchQueryChanged)
    def searchQuery(self): return self._search_query
    @searchQuery.setter
    def searchQuery(self, v: str):
        if v != self._search_query:
            self._search_query = v
            self.searchQueryChanged.emit()
            self._debounce.start()

    @Property(int, notify=sortModeChanged)
    def sortMode(self): return self._sort_mode
    @sortMode.setter
    def sortMode(self, v: int):
        if v != self._sort_mode:
            self._sort_mode = v
            self.sortModeChanged.emit()
            self._rebuild()

    @Property(int, notify=workCountChanged)
    def workCount(self): return self._works.rowCount()

    @Property(bool, notify=isGeneratingDigestChanged)
    def isGeneratingDigest(self): return self._is_generating_digest
    @isGeneratingDigest.setter
    def isGeneratingDigest(self, v: bool):
        if v != self._is_generating_digest:
            self._is_generating_digest = v
            self.isGeneratingDigestChanged.emit()

    @Property(int, notify=digestProgressChanged)
    def digestProgress(self): return self._digest_progress
    @digestProgress.setter
    def digestProgress(self, v: int):
        if v != self._digest_progress:
            self._digest_progress = v
            self.digestProgressChanged.emit()

    @Property(bool, notify=isExtractingSnapshotsChanged)
    def isExtractingSnapshots(self): return self._is_extracting_snapshots
    @isExtractingSnapshots.setter
    def isExtractingSnapshots(self, v: bool):
        if v != self._is_extracting_snapshots:
            self._is_extracting_snapshots = v
            self.isExtractingSnapshotsChanged.emit()

    @Property(str, notify=snapshotProgressMsgChanged)
    def snapshotProgressMsg(self): return self._snapshot_progress_msg
    @snapshotProgressMsg.setter
    def snapshotProgressMsg(self, v: str):
        if v != self._snapshot_progress_msg:
            self._snapshot_progress_msg = v
            self.snapshotProgressMsgChanged.emit()

    # ── Slots ─────────────────────────────────────────

    @Slot()
    def reload(self):
        try:
            from javstory.harvest.database import get_db_session
            from gui.library_data import load_library_summaries_from_session
            session = get_db_session()
            try:
                self._all_summaries = load_library_summaries_from_session(session)
            finally:
                session.close()
            self._rebuild()
            self.summariesReloaded.emit()
            self.toastMessage.emit(f"{len(self._all_summaries)}건 로드", "success")
        except Exception as e:
            self._all_summaries = []
            self._rebuild()
            self.summariesReloaded.emit()
            self.toastMessage.emit(f"DB 로드 실패: {e}", "error")

    @Slot(str)
    def loadDetail(self, product_code: str):
        s = next((x for x in self._all_summaries if x.product_code == product_code), None)
        if not s:
            try:
                from javstory.utils.product_code import strip_split_suffixes
                base = strip_split_suffixes((product_code or "").strip().upper()) or (product_code or "").strip().upper()
                s = next((x for x in self._all_summaries if strip_split_suffixes((x.product_code or "").strip().upper()) == base), None)
            except Exception: pass
        if not s: return

        fp_bind = getattr(s, "folder_path", None) or ""
        data = {
            "product_code": s.product_code,
            "title_ko": s.title_ko,
            "title_ja": s.title_ja,
            "actors_ko": s.actors_ko,
            "maker_ko": s.maker_ko,
            "release_date": s.release_date,
            "synopsis_ko": s.synopsis_ko,
            "genres_ko": s.genres_ko,
            "cover_path": s.cover_effective_path or s.cover_local_path or "",
            "scene_count": s.scene_count,
            "pipeline_stage": s.pipeline_stage,
            "has_canonical": s.has_canonical,
            "overall_summary": s.overall_summary_preview,
            "still_paths": [],
            "video_path": "",
            "is_hardcoded": s.is_hardcoded,
            "has_ja_srt": s.has_ja_srt,
            "has_ko_srt": s.has_ko_srt,
            "lamp_hardcoded": s.lamp_hardcoded,
            "folder_path": fp_bind,
            "digest_path": "",
        }

        try:
            from javstory.library.paths import library_state_path
            p = library_state_path(s.product_code)
            if p.is_file():
                d = json.loads(p.read_text(encoding="utf-8"))
                data["grok_json"] = json.dumps(d.get("story_context", {}), ensure_ascii=False, indent=2)
                stills = []
                for sc in (d.get("scenes") or []):
                    if isinstance(sc, dict):
                        for sp in (sc.get("still_paths") or []):
                            stills.append(str(sp))
                data["still_paths"] = stills
        except Exception: pass

        try:
            from javstory.translation.story_grok_module import story_context_cache_path, merge_story_context_tier
            tier = merge_story_context_tier(None)
            cp = story_context_cache_path(s.product_code, str(tier.get("model") or ""))
            if not cp.is_file():
                cp = story_context_cache_path(s.product_code, "")
            if cp.is_file():
                gj = json.loads(cp.read_text(encoding="utf-8"))
                scenes_raw = gj.get("scenes") or []
                grok_scenes = []
                for sc in scenes_raw:
                    if isinstance(sc, dict):
                        grok_scenes.append({
                            "time_range": sc.get("time_range", ""),
                            "scene_label": sc.get("scene_label", ""),
                            "scene_summary": sc.get("scene_summary", ""),
                        })
                data["grok_scenes_json"] = json.dumps(grok_scenes, ensure_ascii=False)
        except Exception: pass

        stills_set = set()
        if data.get("still_paths"):
            for p in data["still_paths"]: stills_set.add(str(Path(p).resolve()))

        try:
            from javstory.config.app_config import DATA_ROOT
            media_dir = Path(DATA_ROOT) / "media" / s.product_code
            if media_dir.is_dir():
                snap_dir = media_dir / "Snapshots"
                exts = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
                found = []
                if snap_dir.is_dir():
                    for ext in exts: found.extend(snap_dir.glob(ext))
                else:
                    for ext in exts: found.extend(media_dir.glob(ext))
                exclude_names = {"cover.jpg", "poster.jpg", "thumb.jpg", "cover.png", "poster.png", "cover.webp", "poster.webp"}
                for f in found:
                    if f.name.lower() not in exclude_names: stills_set.add(str(f.resolve()))
                
                # mp4 다이제스트 파일 점검 (새로운 digest 전용 폴더 우선 탐색)
                digest_file = media_dir / "digest" / "digest.mp4"
                if not digest_file.exists():
                    digest_file = snap_dir / "digest.mp4"
                if not digest_file.exists():
                    digest_file = media_dir / "digest.mp4"
                if digest_file.is_file():
                    data["digest_path"] = str(digest_file.resolve())

            data["still_paths"] = sorted(list(stills_set))
        except Exception: pass

        try:
            from gui.library_data import guess_video_path_for_product
            vp = guess_video_path_for_product(s.product_code, fp_bind or None)
            if vp:
                data["video_path"] = str(vp)
        except Exception: pass

        self._detail.load(data)
        self.detailLoaded.emit()

    @Slot(str)
    def openFolder(self, product_code: str):
        import os
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata
            session = get_db_session()
            folder_to_open = None
            try:
                row = session.query(JAVMetadata).filter_by(product_code=product_code).first()
                if row and row.folder_path:
                    p = Path(row.folder_path)
                    if p.exists(): folder_to_open = p
            finally: session.close()
            if not folder_to_open:
                from javstory.library.paths import work_library_dir
                d = work_library_dir(product_code)
                if d.is_dir(): folder_to_open = d
            if folder_to_open: os.startfile(folder_to_open)
            else:
                self.toastMessage.emit("저장된 폴더 위치를 찾을 수 없습니다. 폴더를 직접 지정해 주세요.", "warning")
                self.requestFolderSelection.emit(product_code)
        except Exception as e: self.toastMessage.emit(f"폴더 열기 실패: {e}", "error")

    def _bind_folder_impl(self, product_code: str, folder_path: str, force: bool) -> bool:
        try:
            from javstory.utils.product_code import extract_product_code_from_path
            from javstory.harvest.database import get_db_session, JAVMetadata
            from gui.library_data import _first_video_in_dir

            pc = (product_code or "").strip().upper()
            target_path = Path(folder_path)
            if not target_path.is_dir():
                self.toastMessage.emit(f"폴더가 없거나 디렉터리가 아닙니다: {folder_path}", "error")
                return False

            detected_pc = extract_product_code_from_path(target_path)
            if not detected_pc:
                v = _first_video_in_dir(target_path)
                if v:
                    detected_pc = extract_product_code_from_path(v)

            mismatch = not detected_pc or detected_pc.upper() != pc
            if mismatch and not force:
                self.toastMessage.emit(
                    f"선택한 폴더({target_path.name})가 품번 {pc}와 일치하지 않습니다. 강제 연결을 사용하세요.",
                    "error",
                )
                return False

            session = get_db_session()
            try:
                row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                if row:
                    abs_path = str(target_path.resolve())
                    row.folder_path = abs_path
                    session.commit()
                    if mismatch and force:
                        self.toastMessage.emit(f"강제 연결 저장: {abs_path}", "warning")
                    else:
                        self.toastMessage.emit(f"폴더 경로가 저장되었습니다: {abs_path}", "success")
                    self.refreshProduct(pc)
                    self.summariesReloaded.emit()
                    QTimer.singleShot(
                        0,
                        lambda p=pc, fd=abs_path: self._maybe_auto_snapshots_after_folder_bind(p, fd),
                    )
                    return True
                self.toastMessage.emit(f"DB에 품번 {pc} 메타데이터가 없습니다.", "error")
                return False
            finally:
                session.close()
        except Exception as e:
            self.toastMessage.emit(f"폴더 연결 실패: {e}", "error")
            return False

    @Slot(str, str)
    def bindFolder(self, product_code: str, folder_path: str):
        self._bind_folder_impl(product_code, folder_path, False)

    @Slot(str, str, bool, result=bool)
    def bindFolderForced(self, product_code: str, folder_path: str, force: bool) -> bool:
        """force=True면 품번 검증 불일치여도 저장."""
        return self._bind_folder_impl(product_code, folder_path, force)

    @Slot(str, str, result=list)
    def searchFolderBindingCandidates(self, product_code: str, old_path: str) -> list[str]:
        """라이브러리·미디어 루트에서 품번 폴더 후보 경로를 다시 검색한다 (팝업의 ‘다시 검색’용)."""
        from gui.folder_watch_service import search_folder_candidates

        pc = (product_code or "").strip().upper()
        op = (old_path or "").strip()
        return search_folder_candidates(pc, old_path=op if op else None)

    @Slot(str)
    def clearFolderBinding(self, product_code: str):
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata

            pc = (product_code or "").strip().upper()
            if not pc:
                return
            session = get_db_session()
            try:
                row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                if row:
                    row.folder_path = None
                    session.commit()
                    self.toastMessage.emit("폴더 연결이 해제되었습니다.", "success")
                    self.refreshProduct(pc)
                    self.summariesReloaded.emit()
                else:
                    self.toastMessage.emit(f"DB에 품번 {pc}가 없습니다.", "warning")
            finally:
                session.close()
        except Exception as e:
            self.toastMessage.emit(f"연결 해제 실패: {e}", "error")

    @Slot(str)
    def refreshProduct(self, product_code: str):
        try:
            pc = (product_code or "").strip().upper()
            if not pc: return
            found = False
            for i, s in enumerate(self._all_summaries):
                if s.product_code == pc:
                    from gui.library_data import row_to_summary
                    from javstory.harvest.database import get_db_session, JAVMetadata
                    session = get_db_session()
                    try:
                        row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                        if row:
                            new_s = row_to_summary(row)
                            self._all_summaries[i] = new_s
                            found = True
                    finally: session.close()
                    break
            
            if found:
                # 2. 현재 상세 페이지(DetailView)가 해당 품번이면 즉시 다시 로드하여 UI 갱신
                if self._detail.productCode == pc:
                    self.loadDetail(pc)
                # 3. 전체 목록 재구성 필터링 반영
                self._rebuild()
        except Exception as e: print(f"[LibraryModel] 품번 {product_code} 갱신 실패: {e}")

    def _set_detail_editing(self, v: bool) -> None:
        if bool(v) != self._detail_editing:
            self._detail_editing = bool(v)
            self.detailEditingChanged.emit()

    @Slot()
    def beginDetailEdit(self):
        pc = (self._detail.productCode or "").strip().upper()
        if not pc:
            self.toastMessage.emit("품번이 없습니다.", "warning")
            return
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata

            session = get_db_session()
            try:
                row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                if not row:
                    self.toastMessage.emit(f"DB에 품번 {pc}가 없습니다.", "error")
                    return
                self._edit_draft.load_from_row(row)
            finally:
                session.close()

            from javstory.library.detail_persist import load_canonical_for_product

            st = load_canonical_for_product(pc)
            self._scene_edit.load_entries(st.scenes)

            self._set_detail_editing(True)
        except Exception as e:
            self.toastMessage.emit(f"편집 시작 실패: {e}", "error")

    @Slot()
    def cancelDetailEdit(self):
        pc = (self._detail.productCode or "").strip().upper()
        self._set_detail_editing(False)
        if not pc:
            return
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata
            from javstory.library.detail_persist import load_canonical_for_product

            session = get_db_session()
            try:
                row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                if row:
                    self._edit_draft.load_from_row(row)
            finally:
                session.close()
            st = load_canonical_for_product(pc)
            self._scene_edit.load_entries(st.scenes)
        except Exception as e:
            print(f"[LibraryModel] cancelDetailEdit: {e}")

    @Slot(result=bool)
    def saveDetailEdit(self) -> bool:
        pc = (self._edit_draft.productCode or "").strip().upper()
        if not pc:
            self.toastMessage.emit("품번이 없습니다.", "warning")
            return False
        try:
            from javstory.harvest.database import get_db_session, JAVMetadata
            from javstory.library.detail_persist import persist_metadata_row_and_sync_files

            session = get_db_session()
            try:
                row = session.query(JAVMetadata).filter_by(product_code=pc).first()
                if not row:
                    self.toastMessage.emit(f"DB에 품번 {pc}가 없습니다.", "error")
                    return False
                self._edit_draft.apply_to_row(row)
                session.commit()
                session.refresh(row)
                scenes = self._scene_edit.to_entries()
                persist_metadata_row_and_sync_files(pc, row, scenes_override=scenes)
            finally:
                session.close()

            self._set_detail_editing(False)
            self.refreshProduct(pc)
            self.toastMessage.emit("저장되었습니다.", "success")
            return True
        except Exception as e:
            self.toastMessage.emit(f"저장 실패: {e}", "error")
            return False

    @Slot(result=bool)
    def saveSceneEditsOnly(self) -> bool:
        """DB 메타는 건드리지 않고 씬 배열만 library_state + Grok 캐시에 저장."""
        pc = (self._detail.productCode or "").strip().upper()
        if not pc:
            self.toastMessage.emit("품번이 없습니다.", "warning")
            return False
        if not self._detail_editing:
            self.toastMessage.emit("편집 모드에서만 사용할 수 있습니다.", "warning")
            return False
        try:
            from javstory.library.detail_persist import persist_scenes_only

            persist_scenes_only(pc, self._scene_edit.to_entries())
            self.refreshProduct(pc)
            self.toastMessage.emit("씬 저장 완료", "success")
            return True
        except Exception as e:
            self.toastMessage.emit(f"씬 저장 실패: {e}", "error")
            return False

    @Slot(str, str, str, result=bool)
    def insertNewMaker(self, ja: str, ko: str, en: str) -> bool:
        ja, ko, en = (ja or "").strip(), (ko or "").strip(), (en or "").strip()
        if not ja and not ko:
            self.toastMessage.emit("메이커 일본어 또는 한국어를 입력하세요.", "warning")
            return False
        slug = en or ko or ja
        jp = ja or ko
        try:
            from javstory.harvest.database import get_db_session, Maker

            session = get_db_session()
            try:
                existing = session.query(Maker).filter_by(japanese=jp).first()
                if existing:
                    self.toastMessage.emit("같은 일본어 이름의 메이커가 이미 있습니다.", "warning")
                    return False
                session.add(Maker(japanese=jp, korean=ko or None, english=en or None, slug=slug))
                session.commit()
                self._edit_draft.makerJa = jp
                self._edit_draft.makerKo = ko
                self._edit_draft.makerEn = en
                self._edit_draft.makerZhCn = ""
                self._edit_draft.makerZhTw = ""
            finally:
                session.close()
            self.toastMessage.emit("메이커가 추가되었습니다.", "success")
            return True
        except Exception as e:
            self.toastMessage.emit(f"메이커 추가 실패: {e}", "error")
            return False

    @Slot(str, result=list)
    def searchMakers(self, query: str):
        try:
            from sqlalchemy import or_

            from javstory.harvest.database import get_db_session, Maker

            q = (query or "").strip()
            session = get_db_session()
            try:
                qry = session.query(Maker)
                if q:
                    like = f"%{q}%"
                    qry = qry.filter(
                        or_(Maker.japanese.like(like), Maker.korean.like(like), Maker.english.like(like)),
                    )
                rows = qry.order_by(Maker.japanese.asc()).limit(80).all()
                return [
                    {"japanese": r.japanese or "", "korean": r.korean or "", "english": r.english or "", "slug": r.slug or ""}
                    for r in rows
                ]
            finally:
                session.close()
        except Exception as e:
            print(f"[LibraryModel] searchMakers: {e}")
            return []

    @Slot(str, str, str)
    def applyMakerFields(self, ja: str, ko: str, en: str):
        self._edit_draft.makerJa = (ja or "").strip()
        self._edit_draft.makerKo = (ko or "").strip()
        self._edit_draft.makerEn = (en or "").strip()

    @Slot(str, str, str, str, str)
    def setDraftTitles(self, ko: str, ja: str, en: str, zhcn: str, zhtw: str):
        self._edit_draft.titleKo = (ko or "").strip()
        self._edit_draft.titleJa = (ja or "").strip()
        self._edit_draft.titleEn = (en or "").strip()
        self._edit_draft.titleZhCn = (zhcn or "").strip()
        self._edit_draft.titleZhTw = (zhtw or "").strip()

    @Slot(str, str, str, str, str)
    def setDraftSynopses(self, ko: str, ja: str, en: str, zhcn: str, zhtw: str):
        self._edit_draft.synopsisKo = (ko or "").strip()
        self._edit_draft.synopsisJa = (ja or "").strip()
        self._edit_draft.synopsisEn = (en or "").strip()
        self._edit_draft.synopsisZhCn = (zhcn or "").strip()
        self._edit_draft.synopsisZhTw = (zhtw or "").strip()

    @Slot(str, str)
    def insertNewGenre(self, ja: str, ko: str):
        ja, ko = (ja or "").strip(), (ko or "").strip()
        if not ja:
            self.toastMessage.emit("장르 일본어를 입력하세요.", "warning")
            return
        try:
            from javstory.harvest.database import Genre, get_db_session

            session = get_db_session()
            try:
                if session.query(Genre).filter_by(japanese=ja).first():
                    self.toastMessage.emit("같은 일본어 장르가 이미 있습니다.", "warning")
                    return
                session.add(Genre(japanese=ja, korean=ko or None, english=None))
                session.commit()
                cur = (self._edit_draft.genresKo or "").strip()
                add = ko or ja
                self._edit_draft.genresKo = (cur + ", " + add).strip(", ").strip() if cur else add
            finally:
                session.close()
            self.toastMessage.emit("장르가 추가되었습니다.", "success")
        except Exception as e:
            self.toastMessage.emit(f"장르 추가 실패: {e}", "error")

    @Slot(str, result=list)
    def searchGenres(self, query: str):
        try:
            from sqlalchemy import or_

            from javstory.harvest.database import Genre, get_db_session

            q = (query or "").strip()
            session = get_db_session()
            try:
                qry = session.query(Genre)
                if q:
                    like = f"%{q}%"
                    qry = qry.filter(or_(Genre.japanese.like(like), Genre.korean.like(like), Genre.english.like(like)))
                rows = qry.order_by(Genre.japanese.asc()).limit(120).all()
                return [{"japanese": r.japanese or "", "korean": r.korean or "", "english": r.english or ""} for r in rows]
            finally:
                session.close()
        except Exception as e:
            print(f"[LibraryModel] searchGenres: {e}")
            return []

    @Slot(str)
    def appendGenreKo(self, label_ko: str):
        lab = (label_ko or "").strip()
        if not lab:
            return
        cur = (self._edit_draft.genresKo or "").strip()
        parts = [x.strip() for x in cur.split(",") if x.strip()]
        if lab not in parts:
            parts.append(lab)
        self._edit_draft.genresKo = ", ".join(parts)

    @Slot(str)
    def removeGenreChip(self, remove_label: str):
        remove_label = (remove_label or "").strip()
        cur = (self._edit_draft.genresKo or "").strip()
        parts = [x.strip() for x in cur.split(",") if x.strip() and x.strip() != remove_label]
        self._edit_draft.genresKo = ", ".join(parts)

    @Slot(str, str)
    def insertNewActress(self, ja: str, ko: str):
        ja, ko = (ja or "").strip(), (ko or "").strip()
        if not ja:
            self.toastMessage.emit("배우 일본어를 입력하세요.", "warning")
            return
        try:
            from javstory.harvest.database import Actress, get_db_session

            session = get_db_session()
            try:
                if session.query(Actress).filter_by(japanese=ja).first():
                    self.toastMessage.emit("같은 일본어 이름의 배우가 이미 있습니다.", "warning")
                    return
                session.add(Actress(japanese=ja, korean=ko or None, romaji=None))
                session.commit()
                add_ko = ko or ja
                self._edit_draft.append_actor_parallel(add_ko, ja, "", "")
            finally:
                session.close()
            self.toastMessage.emit("배우가 추가되었습니다.", "success")
        except Exception as e:
            self.toastMessage.emit(f"배우 추가 실패: {e}", "error")

    @Slot(str, result=list)
    def searchActresses(self, query: str):
        try:
            from sqlalchemy import or_

            from javstory.harvest.database import Actress, get_db_session

            q = (query or "").strip()
            session = get_db_session()
            try:
                qry = session.query(Actress)
                if q:
                    like = f"%{q}%"
                    qry = qry.filter(or_(Actress.japanese.like(like), Actress.korean.like(like), Actress.romaji.like(like)))
                rows = qry.order_by(Actress.japanese.asc()).limit(120).all()
                return [{"japanese": r.japanese or "", "korean": r.korean or "", "romaji": r.romaji or ""} for r in rows]
            finally:
                session.close()
        except Exception as e:
            print(f"[LibraryModel] searchActresses: {e}")
            return []

    @Slot(str)
    def appendActorKo(self, label_ko: str):
        """레거시: 한국어 표시만 추가(ja/로마자 등은 비움). 피커에서는 appendActorFromPick 사용."""
        lab = (label_ko or "").strip()
        if not lab:
            return
        self._edit_draft.append_actor_parallel(lab, "", "", "")

    @Slot(str, str, str)
    def appendActorFromPick(self, label_ko: str, japanese: str, romaji: str):
        """마스터 배우 목록에서 선택 시 한국어 표시 + 일본어·로마자·영문(en=로마자) 슬롯 기록."""
        ro = romaji or ""
        self._edit_draft.append_actor_parallel(
            label_ko or "",
            japanese or "",
            ro,
            ro,
        )

    @Slot(str)
    def removeActorChip(self, remove_label: str):
        self._edit_draft.remove_actor_by_ko_label(remove_label or "")

    @Slot(str, str)
    def generateSnapshots(self, product_code: str, video_path: str):
        if self._snapshot_worker and self._snapshot_worker.isRunning(): return
        from javstory.config.app_config import DATA_ROOT
        output_dir = Path(DATA_ROOT) / "media" / product_code / "Snapshots"
        
        self.isExtractingSnapshots = True
        self.snapshotProgressMsg = "추출 준비 중..."

        from gui.workers.snapshot_worker import SnapshotWorker
        self._snapshot_worker = SnapshotWorker(product_code, video_path, str(output_dir))
        self._snapshot_worker.progress.connect(self._on_snapshot_progress)
        self._snapshot_worker.finished.connect(self._on_snapshot_finished)
        self._snapshot_worker.start()

    def _on_snapshot_progress(self, curr, total):
        self.snapshotProgress.emit(curr, total)
        self.snapshotProgressMsg = f"추출 중... ({curr}/{total})"

    def _on_snapshot_finished(self, success, message):
        self.isExtractingSnapshots = False
        self.snapshotFinished.emit(success, message)
        if success: self.loadDetail(self._detail.productCode)

    @Slot(str, str)
    def generateDigest(self, product_code: str, video_path: str):
        if self._digest_worker and self._digest_worker.isRunning(): return
        from javstory.config.app_config import DATA_ROOT
        
        self.isGeneratingDigest = True
        self.digestProgress = 0
        
        # 전용 digest 폴더 아래에 digest.mp4 생성
        output_dir = Path(DATA_ROOT) / "media" / product_code / "digest"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "digest.mp4"
        
        from gui.workers.digest_worker import DigestWorker
        self._digest_worker = DigestWorker(product_code, video_path, str(output_path))
        self._digest_worker.finished.connect(self._on_digest_finished)
        self._digest_worker.progressUpdated.connect(self._on_digest_progress)
        self._digest_worker.start()
        self.toastMessage.emit("🎥 다이제스트 타임랩스 추출을 시작합니다...", "info")

    @Slot(int)
    def _on_digest_progress(self, percent: int):
        self.digestProgress = percent

    def _on_digest_finished(self, success, message):
        self.isGeneratingDigest = False
        if success:
            self.toastMessage.emit(message, "success")
            self.loadDetail(self._detail.productCode) # 완료되면 UI 갱신 (digestPath 업데이트)
        else:
            self.toastMessage.emit(message, "error")

    def _maybe_auto_snapshots_after_folder_bind(self, product_code: str, folder_abs: str) -> None:
        """폴더 연결 직후 Snapshots 가 비어 있으면 연결 폴더의 영상에서 스냅샷 자동 추출."""
        try:
            pc = (product_code or "").strip().upper()
            if not pc:
                return
            from gui.library_data import guess_video_path_for_product
            from javstory.config.app_config import DATA_ROOT

            vp = guess_video_path_for_product(pc, folder_abs)
            if vp is None or not vp.is_file():
                return

            snap_dir = Path(DATA_ROOT) / "media" / pc / "Snapshots"
            if snap_dir.is_dir():
                n = 0
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
                    n += len(list(snap_dir.glob(pattern)))
                if n > 0:
                    return

            self.toastMessage.emit("스냅샷이 없어 영상에서 자동 추출을 시작합니다.", "info")
            self.generateSnapshots(pc, str(vp))
        except Exception as e:
            print(f"[LibraryModel] 폴더 연결 후 자동 스냅샷 실패: {e}")

    def _rebuild(self):
        def _base_code(pc: str) -> str:
            try:
                from javstory.utils.product_code import strip_split_suffixes
                u = (pc or "").strip().upper()
                return strip_split_suffixes(u) or u
            except Exception: return (pc or "").strip().upper()

        q = (self._search_query or "").strip().lower()
        filtered = []
        for s in self._all_summaries:
            if q:
                gk = getattr(s, "genres_ko", None) or ""
                blob = f"{s.product_code} {s.title_ko} {s.actors_ko} {gk}".lower()
                if q not in blob:
                    continue
            filtered.append(s)

        groups = {}
        for s in filtered:
            k = _base_code(getattr(s, "product_code", "") or "")
            groups.setdefault(k, []).append(s)

        stage_rank = {"none": 0, "harvest": 1, "transcription": 2, "translation": 3, "canonical": 4}

        def pick_rep(lst):
            def score(x):
                has_cover = 1 if (getattr(x, "cover_effective_path", None) or getattr(x, "cover_local_path", None)) else 0
                upd = getattr(x, "updated_at_iso", "") or ""
                return (has_cover, upd)
            return max(lst, key=score)

        merged_items = []
        for base_pc, lst in groups.items():
            rep = pick_rep(lst)
            max_scene = max((getattr(x, "scene_count", 0) or 0) for x in lst) if lst else 0
            max_stage = "none"
            for x in lst:
                st = getattr(x, "pipeline_stage", "none") or "none"
                if stage_rank.get(st, 0) > stage_rank.get(max_stage, 0): max_stage = st
            merged_items.append({
                "product_code": base_pc,
                "title_ko": getattr(rep, "title_ko", "") or "",
                "title_ja": getattr(rep, "title_ja", "") or "",
                "actors_ko": getattr(rep, "actors_ko", "") or "",
                "cover_path": getattr(rep, "cover_effective_path", None) or getattr(rep, "cover_local_path", None) or "",
                "scene_count": max_scene,
                "pipeline_stage": max_stage,
                "release_date": getattr(rep, "release_date", "") or "",
                "has_canonical": any(bool(getattr(x, "has_canonical", False)) for x in lst),
                "part_count": len(lst),
                "is_hardcoded": any(bool(getattr(x, "is_hardcoded", False)) for x in lst),
                "has_ja_srt": any(bool(getattr(x, "has_ja_srt", False)) for x in lst),
                "has_ko_srt": any(bool(getattr(x, "has_ko_srt", False)) for x in lst),
                "lamp_hardcoded": any(bool(getattr(x, "lamp_hardcoded", False)) for x in lst),
            })

        mode = self._sort_mode
        if mode == 0: merged_items.sort(key=lambda it: it.get("product_code", ""))
        elif mode == 1: merged_items.sort(key=lambda it: it.get("release_date", ""), reverse=True)
        elif mode == 2: merged_items.sort(key=lambda it: it.get("release_date", ""))
        elif mode == 3: merged_items.sort(key=lambda it: int(it.get("scene_count") or 0), reverse=True)

        self._works.refresh(merged_items)
        self.workCountChanged.emit()
