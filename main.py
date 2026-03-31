import sys
import os
from pathlib import Path

# 프로젝트 루트를 import 경로에 포함 (python main.py / IDE 실행 모두)
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core import secrets_manager
try:
    from core import bypass_manager
except ImportError:
    import bypass_manager
from gui.main_window import MainWindow
from gui.settings_dialog import SettingsDialog


def main() -> None:
    # 0. 바이패스(GoodbyeDPI) 백그라운드 구동 시작 (시스템 중복 실행 확인 포함)
    try:
        bypass_manager.manager.start()
    except Exception as e:
        print(f"[System] 바이패스 시작 실패: {e}")

    # 1. secrets_manager 임포트 시 .env 로드됨. keyring 값을 os.environ에 맞춤.
    secrets_manager.apply_env_to_os()

    app = MainWindow()

    # 2. 종료 시 바이패스 세션 정리 (윈도우 닫기 이벤트 핸들링)
    def on_closing():
        print("[System] 종료 중... 바이패스 세션을 정리합니다.")
        try:
            bypass_manager.manager.stop()
        except Exception:
            pass
        app.destroy()
        sys.exit(0)

    app.protocol("WM_DELETE_WINDOW", on_closing)

    # 설정 창 유도 (키가 없을 때만)
    if not secrets_manager.get_openrouter_api_key():
        app.after(150, lambda: SettingsDialog(app, on_saved=app._refresh_env_banner))

    app.mainloop()


if __name__ == "__main__":
    main()
