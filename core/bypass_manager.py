import os
import subprocess
import signal
import sys
import time
from pathlib import Path
from tkinter import messagebox

class BypassManager:
    """GoodbyeDPI를 백그라운드에서 실행하고 관리하는 클래스"""
    def __init__(self, tools_dir=None):
        if tools_dir is None:
            # d:\App\JAVSTORY\core\bypass_manager.py -> d:\App\JAVSTORY\tools
            self.root_dir = Path(__file__).resolve().parent.parent
            self.tools_dir = self.root_dir / "tools" / "goodbyedpi"
        else:
            self.tools_dir = Path(tools_dir)
            
        self.process = None
        self.is_running = False

    def _get_executable_path(self):
        arch = "x86_64" if sys.maxsize > 2**32 else "x86"
        exe_path = self.tools_dir / arch / "goodbyedpi.exe"
        return exe_path

    def _is_external_process_running(self):
        """윈도우 프로세스 목록에서 goodbyedpi.exe가 있는지 확인"""
        try:
            # tasklist 명령어로 확인 (강력하고 외부 라이브러리 불필요)
            output = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq goodbyedpi.exe" /NH',
                shell=True,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000
            ).decode('cp949', errors='ignore')
            return "goodbyedpi.exe" in output.lower()
        except Exception:
            return False

    def start(self):
        # 1. 내부 필래그 확인
        if self.is_running:
            return True
            
        # 2. 시스템 전체 프로세스 중복 확인
        if self._is_external_process_running():
            print("[Bypass] GoodbyeDPI가 이미 시스템에서 실행 중입니다. 별도로 시작하지 않습니다.")
            self.is_running = True # 상태 동기화
            return True
            
        exe_path = self._get_executable_path()
        if not exe_path.exists():
            print(f"[Bypass] GoodbyeDPI를 찾을 수 없습니다: {exe_path}")
            return False

        try:
            # Creation flags to run without console window
            # CREATE_NO_WINDOW = 0x08000000
            self.process = subprocess.Popen(
                [str(exe_path), "-9"],
                cwd=str(exe_path.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000
            )
            self.is_running = True
            print("[Bypass] GoodbyeDPI가 백그라운드에서 시작되었습니다.")
            return True
        except OSError as e:
            # Windows Error 740: ERROR_ELEVATION_REQUIRED
            if getattr(e, 'winerror', None) == 740:
                print("[Bypass] 관리자 권한이 필요합니다.")
                messagebox.showwarning(
                    "관리자 권한 필요",
                    "GoodbyeDPI(우회 기능)를 시작하려면 '관리자 권한'이 필요합니다.\n\n"
                    "우회가 필요한 사이트(JavDB 등)를 이용하시려면,\n"
                    "프로그램을 종료하고 'start.bat'을 마우스 오른쪽 클릭하여\n"
                    "'관리자 권한으로 실행'해 주시기 바랍니다."
                )
            else:
                print(f"[Bypass] OS 에러: {e}")
            return False
        except Exception as e:
            print(f"[Bypass] 기타 실행 에러: {e}")
            return False

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                print("[Bypass] GoodbyeDPI가 종료되었습니다.")
            except Exception:
                try:
                    self.process.kill()
                    print("[Bypass] GoodbyeDPI를 강제 종료했습니다.")
                except:
                    pass
            finally:
                self.process = None
                self.is_running = False

# 싱글톤 인스턴스
manager = BypassManager()
