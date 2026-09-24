"""PC起動(ログイン)時の自動起動の登録/解除。
Windows: HKCU\\...\\Run レジストリ / macOS: ~/Library/LaunchAgents の plist"""
import sys
from pathlib import Path

NAME = "CustomInputKey"
LAUNCHER = Path(__file__).resolve().parent.parent / "CustomInputKey.pyw"


def _command():
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")  # 黒い画面を出さない
    return f'"{pythonw if pythonw.exists() else exe}" "{LAUNCHER}"'


if sys.platform == "win32":
    import winreg

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def is_enabled():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, NAME)
                return True
        except FileNotFoundError:
            return False

    def set_enabled(on):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, NAME)
                except FileNotFoundError:
                    pass

elif sys.platform == "darwin":
    import plistlib

    PLIST = Path.home() / "Library/LaunchAgents" / f"com.{NAME.lower()}.plist"

    def is_enabled():
        return PLIST.exists()

    def set_enabled(on):
        if on:
            PLIST.parent.mkdir(parents=True, exist_ok=True)
            PLIST.write_bytes(plistlib.dumps({
                "Label": f"com.{NAME.lower()}",
                "ProgramArguments": [sys.executable, str(LAUNCHER)],
                "RunAtLoad": True,
            }))
        elif PLIST.exists():
            PLIST.unlink()

else:
    def is_enabled():
        return False

    def set_enabled(on):
        raise OSError("このOSの自動起動には未対応です")
