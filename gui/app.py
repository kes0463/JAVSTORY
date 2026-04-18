"""QML 엔진 초기화 및 Python 모델 등록."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine

_QML_DIR = Path(__file__).resolve().parent / "qml"


def create_engine(app) -> QQmlApplicationEngine:
    """QQmlApplicationEngine을 생성하고 Python 모델을 context에 등록한다."""
    from javstory.harvest.database import init_db
    init_db()

    engine = QQmlApplicationEngine()

    engine.addImportPath(str(_QML_DIR))

    from gui.models.dashboard_model import DashboardModel
    from gui.models.harvest_model import HarvestModel
    from gui.models.processing_model import ProcessingModel
    from gui.models.library_model import LibraryModel
    from gui.models.settings_model import SettingsModel
    from gui.models.folder_explorer_model import FolderExplorerModel
    from gui.folder_binding_inbox_store import FolderBindingInboxStore

    ctx = engine.rootContext()

    print("[UI] Initializing DashboardModel...")
    dashboard = DashboardModel(parent=app)
    print("[UI] Initializing HarvestModel...")
    harvest = HarvestModel(parent=app)
    print("[UI] Initializing ProcessingModel...")
    processing = ProcessingModel(parent=app)
    print("[UI] Initializing LibraryModel...")
    library = LibraryModel(parent=app)
    print("[UI] Initializing SettingsModel...")
    settings = SettingsModel(parent=app)
    print("[UI] Initializing FolderExplorerModel...")
    folder_explorer = FolderExplorerModel(parent=app)
    folder_binding_inbox_store = FolderBindingInboxStore(parent=app)

    print("[UI] Registering context properties...")
    ctx.setContextProperty("DashboardModel", dashboard)
    ctx.setContextProperty("HarvestModel", harvest)
    ctx.setContextProperty("ProcessingModel", processing)
    ctx.setContextProperty("LibraryModel", library)
    ctx.setContextProperty("SettingsModel", settings)
    ctx.setContextProperty("FolderExplorerModel", folder_explorer)
    ctx.setContextProperty("FolderBindingInboxStore", folder_binding_inbox_store)

    from gui.folder_watch_service import FolderMoveWatchService

    _folder_watch = FolderMoveWatchService(library, parent=app)
    library.summariesReloaded.connect(_folder_watch.refresh_paths_from_db)
    QTimer.singleShot(2500, _folder_watch.refresh_paths_from_db)

    print(f"[UI] Loading QML from: {_QML_DIR / 'main.qml'}")
    engine.load(QUrl.fromLocalFile(str(_QML_DIR / "main.qml")))

    if not engine.rootObjects():
        print("[FATAL] main.qml 로드 실패", file=sys.stderr)
        sys.exit(1)

    # Mica 효과 (Windows 11)
    # 일부 환경에서 즉시 적용 시 창 표시 전에 멈추는 경우가 있어, 이벤트 루프 이후로 지연한다.
    QTimer.singleShot(0, lambda: _apply_mica(engine))

    return engine


def _apply_mica(engine: QQmlApplicationEngine) -> None:
    if sys.platform != "win32":
        return
    if os.environ.get("JAVSTORY_DISABLE_MICA", "").strip().lower() in {"1", "true", "yes"}:
        print("[UI] Mica 비활성화: JAVSTORY_DISABLE_MICA")
        return
    try:
        import win32mica
        import darkdetect

        root = engine.rootObjects()[0]
        hwnd = int(root.winId())
        mode = (
            win32mica.MicaTheme.DARK
            if darkdetect.isDark()
            else win32mica.MicaTheme.LIGHT
        )
        win32mica.ApplyMica(hwnd, mode)
    except Exception as exc:
        print(f"[UI] Mica 효과 적용 실패 (무시됨): {exc}")
