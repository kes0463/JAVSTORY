"""메인 창: CustomTkinter + tkinterdnd2 드롭 + 콘솔 Rich 출력."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Iterable

import customtkinter as ctk
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from tkinterdnd2 import DND_FILES, TkinterDnD

from core.app_config import APP_DISPLAY_TITLE, VIDEO_EXTENSIONS
from core import secrets_manager
from core.pipeline_stubs import run_full_pipeline_dummy
from gui.settings_dialog import SettingsDialog


console = Console()


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        try:
            self.TkdndVersion = TkinterDnD._require(self)
        except Exception:
            self.TkdndVersion = None

        self._video_paths: list[str] = []

        self.title(APP_DISPLAY_TITLE)
        self.geometry("920x640")
        self.minsize(720, 480)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._build_ui()

        if self.TkdndVersion is None:
            self._log_banner(
                "[yellow]tkinterdnd2 초기화 실패[/]: 파일 드롭은 비활성일 수 있습니다. pip 설치와 Tcl/tkdnd를 확인하세요."
            )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top,
            text=APP_DISPLAY_TITLE,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            top,
            text="설정 (API 키)",
            width=140,
            command=self._open_settings,
        ).grid(row=0, column=1, sticky="e")

        drop_hint = ctk.CTkLabel(
            self,
            text="영상 파일 또는 폴더를 아래 목록으로 드래그 앤 드롭 하거나, 버튼으로 추가하세요.",
            text_color=("gray30", "gray65"),
        )
        drop_hint.grid(row=1, column=0, padx=20, pady=(0, 6), sticky="w")

        list_frame = ctk.CTkFrame(self, corner_radius=8)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        inner_bg = "#2b2b2b"
        self._list_host = tk.Frame(list_frame, bg=inner_bg)
        self._list_host.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        bg = "#1e1e1e"
        fg = "#d4d4d4"
        select_bg = "#1f538d"
        self.listbox = tk.Listbox(
            self._list_host,
            font=("Consolas", 11),
            bg=bg,
            fg=fg,
            selectbackground=select_bg,
            selectforeground="white",
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
        )
        sb = ctk.CTkScrollbar(self._list_host, command=self.listbox.yview, orientation="vertical")
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        if self.TkdndVersion is not None:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="ew", padx=16, pady=4)
        for i in range(5):
            btn_row.grid_columnconfigure(i, weight=1 if i == 4 else 0)

        ctk.CTkButton(btn_row, text="파일 추가", command=self._add_files).grid(
            row=0, column=0, padx=4, pady=4
        )
        ctk.CTkButton(btn_row, text="폴더 추가", command=self._add_folder).grid(
            row=0, column=1, padx=4, pady=4
        )
        ctk.CTkButton(btn_row, text="선택 삭제", command=self._remove_selected).grid(
            row=0, column=2, padx=4, pady=4
        )
        ctk.CTkButton(btn_row, text="전체 비우기", command=self._clear_list).grid(
            row=0, column=3, padx=4, pady=4
        )

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=16, pady=(8, 16))
        bottom.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkLabel(bottom, text="대기 중")
        self._progress.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            bottom,
            text="일괄 분석 시작",
            width=160,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_pipeline,
        ).grid(row=0, column=1, sticky="e")

    def _open_settings(self) -> None:
        SettingsDialog(self, on_saved=self._refresh_env_banner)

    def _refresh_env_banner(self) -> None:
        secrets_manager.apply_env_to_os()
        if secrets_manager.get_openrouter_api_key():
            self._progress.configure(text="API 키가 설정되었습니다. 대기 중")

    def _on_drop(self, event) -> None:
        raw = event.data
        try:
            paths = list(self.tk.splitlist(raw))
        except tk.TclError:
            paths = [raw]

        cleaned: list[str] = []
        for p in paths:
            s = p.strip().strip("{}").strip('"')
            if not s:
                continue
            cleaned.append(os.path.normpath(s))

        self._ingest_paths(cleaned)

    def _ingest_paths(self, paths: Iterable[str]) -> None:
        for path in paths:
            if not os.path.exists(path):
                continue
            if os.path.isdir(path):
                self._walk_videos_into_list(path)
            elif path.lower().endswith(VIDEO_EXTENSIONS):
                self._add_single_path(path)

    def _add_single_path(self, path: str) -> None:
        norm = os.path.normpath(path)
        if norm not in self._video_paths:
            self._video_paths.append(norm)
            self.listbox.insert(tk.END, norm)

    def _walk_videos_into_list(self, folder: str) -> None:
        for root, _, files in os.walk(folder):
            for name in files:
                if name.lower().endswith(VIDEO_EXTENSIONS):
                    full = os.path.normpath(os.path.join(root, name))
                    if full not in self._video_paths:
                        self._video_paths.append(full)
                        self.listbox.insert(tk.END, full)

    def _add_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)
        files = filedialog.askopenfilenames(
            title="영상 파일 선택",
            filetypes=(
                ("Video", patterns),
                ("All", "*.*"),
            ),
        )
        self._ingest_paths(files)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="영상 폴더 선택")
        if folder:
            self._ingest_paths([folder])

    def _remove_selected(self) -> None:
        sel = list(self.listbox.curselection())
        for i in reversed(sel):
            self.listbox.delete(i)
            del self._video_paths[i]

    def _clear_list(self) -> None:
        self.listbox.delete(0, tk.END)
        self._video_paths.clear()

    def _log_banner(self, subtitle: str) -> None:
        console.print(
            Panel.fit(
                f"[bold cyan]{APP_DISPLAY_TITLE}[/]\n{subtitle}",
                border_style="cyan",
            )
        )

    def _start_pipeline(self) -> None:
        if not secrets_manager.get_openrouter_api_key():
            messagebox.showwarning(
                "API 키 필요",
                "설정에서 OpenRouter API 키를 먼저 저장해 주세요.",
            )
            self._open_settings()
            return

        if not self._video_paths:
            messagebox.showwarning("목록 비어 있음", "처리할 영상을 추가해 주세요.")
            return

        self._progress.configure(text="콘솔 진행 중… (더미 파이프라인)")

        def worker(paths: list[str]) -> None:
            self._log_banner(
                f"[green]더미 파이프라인[/] · 파일 {len(paths)}개 · 터미널에 단계별 출력"
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task("파일 처리", total=len(paths))
                for path in paths:
                    run_full_pipeline_dummy([path])
                    progress.advance(task)
            console.print("[bold green]더미 실행 완료[/] · 실제 로직은 이후 Phase에서 연결")

            self.after(0, lambda: self._progress.configure(text="대기 중"))

        threading.Thread(
            target=worker,
            args=(list(self._video_paths),),
            daemon=True,
        ).start()
