"""アプリのバージョンと最終更新日。
バージョンは機能を追加したらここを手で上げる。最終更新日は git の最新コミットから自動で取る。"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VERSION = "1.2.0"

ROOT = Path(__file__).resolve().parent.parent


def _git(*args):
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                         timeout=3, **kw)
    return out.stdout.strip() if out.returncode == 0 else ""


def last_updated():
    """(日時文字列, コミットID)。git が無ければファイルの更新日時を使う。"""
    try:
        line = _git("log", "-1", "--format=%cd|%h", "--date=format:%Y-%m-%d %H:%M")
        if line:
            date, commit = line.split("|")
            return date, commit
    except (OSError, subprocess.SubprocessError):
        pass
    newest = max(p.stat().st_mtime for p in Path(__file__).parent.glob("*.py"))
    return datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M"), ""
