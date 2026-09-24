"""音の鳴らない自作ポップアップ。親ウィンドウの中央に表示する。
tkinter.messagebox と同じ呼び方 (showinfo / showerror / askyesno) で使える。"""
import tkinter as tk
from tkinter import ttk

ICONS = {"info": ("ℹ", "#2e7dd7"), "error": ("✖", "#d9534f"), "warning": ("⚠", "#e0a800")}


def _dialog(title, message, kind, buttons, parent=None):
    parent = parent or tk._default_root
    top = tk.Toplevel(parent)
    top.withdraw()
    top.title(title)
    top.resizable(False, False)
    top.transient(parent)
    result = {"value": False}

    body = ttk.Frame(top, padding=(20, 16))
    body.pack(fill="both", expand=True)
    sym, color = ICONS[kind]
    tk.Label(body, text=sym, fg=color, font=("", 22, "bold")).pack(side="left", padx=(0, 14), anchor="n")
    ttk.Label(body, text=message, justify="left", wraplength=360).pack(side="left", anchor="w")

    bar = ttk.Frame(top, padding=(12, 0, 12, 12))
    bar.pack(fill="x")

    def close(value):
        result["value"] = value
        top.grab_release()
        top.destroy()

    for text, value in reversed(buttons):
        b = ttk.Button(bar, text=text, width=10, command=lambda v=value: close(v))
        b.pack(side="right", padx=4)
    focus = bar.winfo_children()[-1]  # 最初のボタン(はい/OK)
    top.bind("<Return>", lambda e: close(buttons[0][1]))
    top.bind("<Escape>", lambda e: close(buttons[-1][1]))
    top.protocol("WM_DELETE_WINDOW", lambda: close(buttons[-1][1]))

    # 親ウィンドウ(隠れていれば画面)の中央に配置
    top.update_idletasks()
    w, h = top.winfo_reqwidth(), top.winfo_reqheight()
    if parent.winfo_viewable():
        cx = parent.winfo_rootx() + parent.winfo_width() // 2
        cy = parent.winfo_rooty() + parent.winfo_height() // 2
    else:
        cx, cy = top.winfo_screenwidth() // 2, top.winfo_screenheight() // 2
    top.geometry(f"+{cx - w // 2}+{cy - h // 2}")
    top.deiconify()
    top.grab_set()
    focus.focus_set()
    top.wait_window()
    return result["value"]


def showinfo(title, message, **kw):
    _dialog(title, message, "info", [("OK", True)], kw.get("parent"))


def showerror(title, message, **kw):
    _dialog(title, message, "error", [("OK", True)], kw.get("parent"))


def askyesno(title, message, icon="info", **kw):
    return _dialog(title, message, icon if icon in ICONS else "info",
                   [("はい", True), ("いいえ", False)], kw.get("parent"))
