"""설정 모델: API 키, 경로, 테마, 모델, 옵션 관리."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

_ROOT = Path(__file__).resolve().parent.parent.parent


class SettingsModel(QObject):
    apiKeyChanged = Signal()
    ollamaUrlChanged = Signal()
    mediaRootChanged = Signal()
    whisperModelChanged = Signal()
    translationProfileChanged = Signal()
    grokEnabledChanged = Signal()
    dpiBypassChanged = Signal()
    themeModeChanged = Signal()
    isSystemDarkChanged = Signal()
    correctionProfileChanged = Signal()
    toastMessage = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        print("[SettingsModel] Loading values...")
        self._load_values()
        print("[SettingsModel] Initialization complete.")
        # 테마 리스너는 안정화될 때까지 비활성화 유지 (필요 시 주석 제거)
        # self._start_theme_listener()

    def _start_theme_listener(self):
        """시스템 테마 변화 감지 시작."""
        print("[SettingsModel] Starting theme listener...")
        try:
            import darkdetect
            darkdetect.listener(lambda _: self.isSystemDarkChanged.emit())
        except Exception:
            pass

    def _load_values(self):
        from javstory.config.app_config import OLLAMA_BASE_URL, MEDIA_ROOT
        try:
            from javstory.config import secrets_manager
            self._api_key = secrets_manager.get_openrouter_api_key() or ""
        except Exception:
            self._api_key = ""
        
        # 1. API 및 미디어
        self._ollama_url = os.environ.get("JAVSTORY_OLLAMA_URL", OLLAMA_BASE_URL)
        self._media_root = os.environ.get("JAVSTORY_MEDIA_ROOT", str(MEDIA_ROOT))
        
        # 2. 모델 및 번역
        self._whisper_model = os.environ.get("JAVSTORY_WHISPER_MODEL", "large-v2")
        self._translation_profile = os.environ.get("JAVSTORY_TRANSLATION_PROFILE", "default").lower()
        
        # 3. 기능 토글
        grok = os.environ.get("JAVSTORY_STORY_ANALYSIS_ENABLED", "1").strip().lower()
        self._grok_enabled = grok in ("1", "true", "yes", "on")
        dpi = os.environ.get("JAVSTORY_DPI_BYPASS_ENABLED", "0").strip().lower()
        self._dpi_bypass = dpi in ("1", "true", "yes", "on")

        # 4. 교정 (Correction) 모델
        self._correction_profile = os.environ.get("JAVSTORY_CORRECTION_PASS2_MODEL", "qwen/qwen3-235b-a22b-2507")
        
        # 5. 외관 (테마)
        try:
            self._theme_mode = int(os.environ.get("JAVSTORY_THEME_MODE", "0"))
        except ValueError:
            self._theme_mode = 0

    # ── Properties ────────────────────────────────────

    @Property(str, notify=apiKeyChanged)
    def apiKey(self): return self._api_key
    @apiKey.setter  # type: ignore[attr-defined]
    def apiKey(self, v):
        if v != self._api_key:
            self._api_key = v; self.apiKeyChanged.emit()

    @Property(str, notify=ollamaUrlChanged)
    def ollamaUrl(self): return self._ollama_url
    @ollamaUrl.setter  # type: ignore[attr-defined]
    def ollamaUrl(self, v):
        if v != self._ollama_url:
            self._ollama_url = v; self.ollamaUrlChanged.emit()

    @Property(str, notify=mediaRootChanged)
    def mediaRoot(self): return self._media_root
    @mediaRoot.setter  # type: ignore[attr-defined]
    def mediaRoot(self, v):
        if v != self._media_root:
            self._media_root = v; self.mediaRootChanged.emit()

    @Property(str, notify=whisperModelChanged)
    def whisperModel(self): return self._whisper_model
    @whisperModel.setter  # type: ignore[attr-defined]
    def whisperModel(self, v):
        if v != self._whisper_model:
            self._whisper_model = v; self.whisperModelChanged.emit()

    @Property(str, notify=translationProfileChanged)
    def translationProfile(self): return self._translation_profile
    @translationProfile.setter  # type: ignore[attr-defined]
    def translationProfile(self, v):
        if v != self._translation_profile:
            self._translation_profile = v; self.translationProfileChanged.emit()

    @Property(bool, notify=grokEnabledChanged)
    def grokEnabled(self): return self._grok_enabled
    @grokEnabled.setter  # type: ignore[attr-defined]
    def grokEnabled(self, v):
        if v != self._grok_enabled:
            self._grok_enabled = v; self.grokEnabledChanged.emit()

    @Property(str, notify=correctionProfileChanged)
    def correctionProfile(self): return self._correction_profile
    @correctionProfile.setter  # type: ignore[attr-defined]
    def correctionProfile(self, v):
        if v != self._correction_profile:
            self._correction_profile = v; self.correctionProfileChanged.emit()

    @Property(bool, notify=dpiBypassChanged)
    def dpiBypass(self): return self._dpi_bypass
    @dpiBypass.setter  # type: ignore[attr-defined]
    def dpiBypass(self, v):
        if v != self._dpi_bypass:
            self._dpi_bypass = v; self.dpiBypassChanged.emit()

    @Property(int, notify=themeModeChanged)
    def themeMode(self): return self._theme_mode
    @themeMode.setter  # type: ignore[attr-defined]
    def themeMode(self, v):
        if v != self._theme_mode:
            self._theme_mode = v
            from javstory.config.secrets_manager import set_env_runtime_value
            set_env_runtime_value("JAVSTORY_THEME_MODE", str(v))
            self.themeModeChanged.emit()
            self._apply_mica_global()

    @Property(bool, notify=isSystemDarkChanged)
    def isSystemDark(self):
        try:
            import darkdetect
            return darkdetect.isDark()
        except Exception:
            return True

    def _apply_mica_global(self):
        """변경된 테마에 맞춰 Mica 효과 재적용."""
        if sys.platform != "win32": return
        try:
            import win32mica
            # 현재 활성화된 메인 윈도우 찾기
            from PySide6.QtWidgets import QApplication
            for top_level_widget in QApplication.topLevelWidgets():
                if top_level_widget.inherits("QQuickWindow"):
                    hwnd = int(top_level_widget.winId())
                    is_dark = self.isSystemDark if self._theme_mode == 0 else (self._theme_mode == 2)
                    mode = win32mica.MicaTheme.DARK if is_dark else win32mica.MicaTheme.LIGHT
                    win32mica.ApplyMica(hwnd, mode)
        except Exception:
            pass

    # ── Slots ─────────────────────────────────────────

    @Slot()
    def saveApiKey(self):
        key = self._api_key.strip()
        if not key:
            self.toastMessage.emit("API 키를 입력하세요.", "warning")
            return
        try:
            from javstory.config.secrets_manager import set_openrouter_api_key, set_env_runtime_value
            set_openrouter_api_key(key)
            if self._ollama_url.strip():
                set_env_runtime_value("JAVSTORY_OLLAMA_URL", self._ollama_url.strip())
            self.toastMessage.emit("API 키 저장 완료", "success")
        except Exception as e:
            self.toastMessage.emit(f"API 키 저장 실패: {e}", "error")

    @Slot()
    def savePaths(self):
        from javstory.config.secrets_manager import set_env_runtime_value
        if self._media_root.strip():
            set_env_runtime_value("JAVSTORY_MEDIA_ROOT", self._media_root.strip())
        self.toastMessage.emit("경로 설정 적용 완료", "success")

    @Slot()
    def saveOptions(self):
        from javstory.config.secrets_manager import set_env_runtime_value
        set_env_runtime_value("JAVSTORY_WHISPER_MODEL", self._whisper_model)
        set_env_runtime_value("JAVSTORY_TRANSLATION_PROFILE", self._translation_profile)
        set_env_runtime_value("JAVSTORY_STORY_ANALYSIS_ENABLED", "1" if self._grok_enabled else "0")
        set_env_runtime_value("JAVSTORY_CORRECTION_PASS2_MODEL", self._correction_profile)
        set_env_runtime_value("JAVSTORY_DPI_BYPASS_ENABLED", "1" if self._dpi_bypass else "0")

        # DPI 우회 연결
        try:
            from javstory.utils.bypass_manager import BypassManager
            bm = BypassManager()
            if self._dpi_bypass:
                bm.start()
            else:
                bm.stop()
        except Exception:
            pass

        self.toastMessage.emit("옵션 저장 완료", "success")

    @Slot(result=str)
    def browseFolder(self):
        """QML에서 호출: 네이티브 폴더 선택 대화상자 (단일)."""
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(None, "폴더 선택")
        return d or ""

    @Slot(result=str)
    def browseFile(self):
        """QML에서 호출: 네이티브 파일 선택 대화상자."""
        from PySide6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(None, "파일 선택", "", "Videos (*.mp4 *.mkv *.avi *.wmv)")
        return f or ""
