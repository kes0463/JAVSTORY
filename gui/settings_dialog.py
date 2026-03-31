"""API 키 입력: CustomTkinter + keyring + .env 동기화."""
from __future__ import annotations

import customtkinter as ctk
from typing import Callable, Optional

from core.app_config import APP_DISPLAY_TITLE, ENV_OPENROUTER_API_KEY
from core import secrets_manager


class SettingsDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master: ctk.CTk,
        *,
        on_saved: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master)
        self._on_saved = on_saved

        self.title(f"{APP_DISPLAY_TITLE} — API 설정")
        self.geometry("520x280")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.grid_columnconfigure(0, weight=1)
        self._build_ui()

        self.transient(master)
        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        pad = {"padx": 20, "pady": (12, 6)}
        ctk.CTkLabel(
            self,
            text="OpenRouter API 키",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", **pad)

        ctk.CTkLabel(
            self,
            text=(
                "키는 Windows 자격 증명(keyring)에 저장되며, "
                "같은 폴더의 .env에도 동기화됩니다."
            ),
            text_color=("gray30", "gray70"),
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        existing = secrets_manager.get_openrouter_api_key() or ""
        self._entry = ctk.CTkEntry(
            self,
            placeholder_text=ENV_OPENROUTER_API_KEY,
            show="*",
            width=440,
            height=36,
        )
        self._entry.grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        if existing:
            self._entry.insert(0, existing)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=20, pady=16)
        btn_row.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(btn_row, text="저장", command=self._save).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            btn_row,
            text="keyring에서 삭제",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self._clear_keyring,
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(btn_row, text="닫기", command=self._on_close).grid(
            row=0, column=2, padx=4
        )

        self._status = ctk.CTkLabel(self, text="", text_color="#3B8ED0")
        self._status.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 12))

    def _save(self) -> None:
        raw = self._entry.get().strip()
        if not raw:
            self._status.configure(text="키를 입력해 주세요.", text_color="#C84B4B")
            return
        try:
            secrets_manager.set_openrouter_api_key(raw, write_env_file=True)
            secrets_manager.apply_env_to_os()
        except ValueError as e:
            self._status.configure(text=str(e), text_color="#C84B4B")
            return
        self._status.configure(text="저장되었습니다.", text_color="#2DC26B")
        if self._on_saved:
            self._on_saved()
        self.after(400, self._on_close)

    def _clear_keyring(self) -> None:
        secrets_manager.clear_openrouter_api_key_from_keyring()
        self._entry.delete(0, "end")
        self._status.configure(
            text="keyring 항목을 삭제했습니다. .env는 그대로일 수 있습니다.",
            text_color="#D9A441",
        )

    def _on_close(self) -> None:
        self.grab_release()
        self.destroy()
