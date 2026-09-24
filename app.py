"""Custom Input Key - キーリマップ & マクロ設定GUI"""
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from pynput import keyboard

from engine import NAMES, Engine
from functions import CHOICE_OF, CHOICES, FUNCTIONS
from keytables import ALL_KEYS, MOD_ALIASES, parse_combo

CONFIG_PATH = Path(__file__).with_name("config.json")
DEFAULT = {
    "remaps": {"caps_lock": "ctrl_l"},
    "macros": [
        {"hotkey": "ctrl+alt+m", "actions": [
            {"type": "text", "value": "よろしくお願いします。"},
            {"type": "key", "value": "enter"}]},
    ],
}
HELP = ("1行に1アクション:\n  text: 入力する文字    key: enter    combo: ctrl+c\n"
        "  wait: 0.5 (秒)    func: 機能 (下で選んで挿入)    open: ファイル/URL/アプリのパス")


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return DEFAULT


def actions_to_text(actions):
    return "\n".join(f"{a['type']}: {a.get('value', '')}" for a in actions)


def text_to_actions(text):
    acts = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        kind, sep, val = line.partition(":")
        kind = kind.strip().lower()
        if not sep or kind not in ("text", "key", "combo", "wait", "func", "open"):
            raise ValueError(f"{n}行目の形式が不正です: {line}")
        val = val[1:] if val.startswith(" ") else val
        if kind in ("key", "combo"):
            parse_combo(val)
        elif kind == "wait":
            float(val)
        elif kind == "func" and val.strip() not in FUNCTIONS:
            raise ValueError(f"{n}行目: 不明な機能 {val}")
        acts.append({"type": kind, "value": val})
    return acts


def key_name(key):
    """pynputのキー -> keytablesのキー名"""
    vk = getattr(getattr(key, "value", key), "vk", None)
    name = NAMES.get(vk)
    if name:
        return name
    ch = getattr(key, "char", None)
    return ch.lower() if ch else None


class KeyCapture:
    """実際にキーを押させて判定する。最初のキーが離された時点で確定。
    on_done(押した順のキー名リスト) を呼ぶ(タイムアウト時は空リスト)。"""

    def __init__(self, on_done, timeout=5.0):
        self.keys, self.on_done, self.done = [], on_done, False
        self.listener = keyboard.Listener(on_press=self._press, on_release=self._release, suppress=True)
        self.listener.start()
        self.timer = __import__("threading").Timer(timeout, self._finish)
        self.timer.start()

    def _press(self, key):
        name = key_name(key)
        if name and name not in self.keys:
            self.keys.append(name)

    def _release(self, key):
        if self.keys:
            self._finish()

    def _finish(self):
        if self.done:
            return
        self.done = True
        self.timer.cancel()
        self.listener.stop()
        self.on_done(list(self.keys))


def keys_to_hotkey(keys):
    """押した順のキー -> 'ctrl+space+j' 形式(修飾キーを先頭に)"""
    if not keys:
        return ""
    *pre, last = keys
    mods = [MOD_ALIASES[k] for k in pre if k in MOD_ALIASES]
    others = [k for k in pre if k not in MOD_ALIASES]
    return "+".join(dict.fromkeys(mods + others + [MOD_ALIASES.get(last, last)]))


class Table(ttk.Frame):
    """全セルに区切り線のある表。クリックで行を選択。"""
    LINE, SEL = "#b0b0b0", "#cce4ff"

    def __init__(self, parent, headings):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=1, highlightbackground=self.LINE)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=self.LINE)  # 背景色が線として見える
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        for c in range(len(headings)):
            self.inner.columnconfigure(c, weight=1, uniform="col")
        for c, h in enumerate(headings):
            tk.Label(self.inner, text=h, bg="#e8e8e8", anchor="center", pady=3
                     ).grid(row=0, column=c, sticky="nsew", padx=(1, 1), pady=(1, 1))
        self.rows, self.selected = [], None

    def insert(self, values):
        cells = []
        for c, v in enumerate(values):
            lb = tk.Label(self.inner, text=v, bg="white", anchor="w", padx=6, pady=3)
            lb.bind("<Button-1>", lambda e, r=len(self.rows): self.select(r))
            cells.append(lb)
        self.rows.append([list(values), cells])
        self._layout()

    def _layout(self):
        for r, (_, cells) in enumerate(self.rows, 1):
            for c, lb in enumerate(cells):
                lb.grid(row=r, column=c, sticky="nsew", padx=(1, 1), pady=(0, 1))
                lb.bind("<Button-1>", lambda e, i=r - 1: self.select(i))
                lb.config(bg=self.SEL if r - 1 == self.selected else "white")

    def select(self, i):
        self.selected = i
        self._layout()

    def values(self):
        return [v for v, _ in self.rows]

    def delete(self, i):
        for lb in self.rows.pop(i)[1]:
            lb.destroy()
        self.selected = None
        self._layout()

    def delete_selected(self):
        if self.selected is not None:
            self.delete(self.selected)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Custom Input Key")
        self.geometry("640x520")
        self.config_data = load_config()
        self.engine = Engine(self.config_data, log=self.log)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.run_btn = tk.Button(top, width=6, relief="flat", font=("", 10, "bold"),
                                 fg="white", command=self.toggle)
        self.run_btn.pack(side="left")
        self._show_switch(False)
        ttk.Button(top, text="保存して反映", command=self.save).pack(side="left", padx=6)
        self.status = ttk.Label(top, text="停止中", foreground="gray")
        self.status.pack(side="left", padx=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8)
        nb.add(self._remap_tab(nb), text="キー変更")
        nb.add(self._macro_tab(nb), text="マクロ")

        self.logbox = tk.Text(self, height=6, state="disabled")
        self.logbox.pack(fill="x", padx=8, pady=8)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if sys.platform == "darwin":
            self.log("macOS: システム設定 > プライバシーとセキュリティ > アクセシビリティ と 入力監視 でこのアプリ(ターミナル/Python)を許可してください")

    # ---------- キー変更タブ ----------
    def _remap_tab(self, parent):
        f = ttk.Frame(parent, padding=8)
        self.remap_tree = Table(f, ["押したキー", "→ 置き換え後"])
        self.remap_tree.pack(fill="both", expand=True)
        for s, d in self.config_data.get("remaps", {}).items():
            self.remap_tree.insert((s, CHOICE_OF.get(d, d)))
        row = ttk.Frame(f)
        row.pack(fill="x", pady=6)
        self.src_cb = ttk.Combobox(row, values=ALL_KEYS, width=14)
        self.dst_cb = ttk.Combobox(row, values=list(CHOICES) + ALL_KEYS, width=24)
        self.src_cb.pack(side="left")
        ttk.Button(row, text="⌨", width=3, command=lambda: self.capture_combo(self.src_cb.set)).pack(side="left")
        ttk.Label(row, text="→").pack(side="left", padx=4)
        self.dst_cb.pack(side="left")
        ttk.Button(row, text="⌨", width=3, command=lambda: self.capture_combo(self.dst_cb.set)).pack(side="left")
        ttk.Button(row, text="追加", command=self.add_remap).pack(side="left", padx=6)
        ttk.Button(row, text="選択を削除",
                   command=self.remap_tree.delete_selected
                   ).pack(side="left")
        return f

    def add_remap(self):
        s, d = self.src_cb.get().strip(), self.dst_cb.get().strip()
        try:
            parse_combo(s)
            if d not in CHOICES:
                parse_combo(d)
        except ValueError as e:
            messagebox.showerror("エラー", f"キー指定が不正です: {e}")
            return
        for i, v in enumerate(self.remap_tree.values()):
            if v[0] == s:
                self.remap_tree.delete(i)
                break
        self.remap_tree.insert((s, d))

    # ---------- マクロタブ ----------
    def _macro_tab(self, parent):
        f = ttk.Frame(parent, padding=8)
        left = ttk.Frame(f)
        left.pack(side="left", fill="y")
        self.macro_list = tk.Listbox(left, width=20, exportselection=False)
        self.macro_list.pack(fill="y", expand=True)
        self.macro_list.bind("<<ListboxSelect>>", self.show_macro)
        ttk.Button(left, text="新規", command=self.new_macro).pack(fill="x")
        ttk.Button(left, text="削除", command=self.del_macro).pack(fill="x")

        right = ttk.Frame(f)
        right.pack(side="left", fill="both", expand=True, padx=8)
        ttk.Label(right, text="ホットキー (例: ctrl+alt+m / space+j = スペース押しながらJ)").pack(anchor="w")
        hk_row = ttk.Frame(right)
        hk_row.pack(fill="x")
        self.hotkey_entry = ttk.Entry(hk_row)
        self.hotkey_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(hk_row, text="⌨ キーを押して設定", command=self.capture_hotkey).pack(side="left", padx=4)
        ttk.Label(right, text=HELP, foreground="gray").pack(anchor="w", pady=4)
        self.actions_text = tk.Text(right, height=10)
        self.actions_text.pack(fill="both", expand=True)
        ins = ttk.Frame(right)
        ins.pack(fill="x", pady=(4, 0))
        self.func_cb = ttk.Combobox(ins, values=list(CHOICES), state="readonly", width=28)
        self.func_cb.pack(side="left")
        ttk.Button(ins, text="機能を挿入", command=self.insert_func).pack(side="left", padx=4)
        ttk.Button(ins, text="⌨ キーを挿入", command=lambda: self.capture_combo(
            lambda c: self._insert_line(f"combo: {c}"))).pack(side="left")
        ttk.Button(right, text="このマクロを確定", command=self.commit_macro).pack(anchor="e", pady=4)

        self.macros = list(self.config_data.get("macros", []))
        self.refresh_macros()
        return f

    def refresh_macros(self):
        self.macro_list.delete(0, "end")
        for m in self.macros:
            self.macro_list.insert("end", m["hotkey"])

    def show_macro(self, _=None):
        sel = self.macro_list.curselection()
        if not sel:
            return
        m = self.macros[sel[0]]
        self.hotkey_entry.delete(0, "end")
        self.hotkey_entry.insert(0, m["hotkey"])
        self.actions_text.delete("1.0", "end")
        self.actions_text.insert("1.0", actions_to_text(m["actions"]))

    def new_macro(self):
        self.macro_list.selection_clear(0, "end")
        self.hotkey_entry.delete(0, "end")
        self.actions_text.delete("1.0", "end")

    def del_macro(self):
        sel = self.macro_list.curselection()
        if sel:
            del self.macros[sel[0]]
            self.refresh_macros()
            self.new_macro()

    def commit_macro(self):
        try:
            hk = self.hotkey_entry.get().strip()
            parse_combo(hk)
            acts = text_to_actions(self.actions_text.get("1.0", "end"))
        except ValueError as e:
            messagebox.showerror("エラー", str(e))
            return
        m = {"hotkey": hk, "actions": acts}
        sel = self.macro_list.curselection()
        if sel:
            self.macros[sel[0]] = m
        else:
            self.macros.append(m)
        self.refresh_macros()
        self.log(f"マクロ確定: {hk} (保存で反映)")

    # ---------- キー入力で判定 ----------
    def _capture(self, apply):
        was_running = bool(self.engine.listener)
        self.engine.stop()  # 設定中はリマップ/マクロを止める
        self.status.config(text="キーを押してください… (5秒)", foreground="orange")

        def done(keys):
            def ui():
                if keys:
                    apply(keys)
                    self.log(f"判定: {' + '.join(keys)}")
                else:
                    self.log("キー入力がありませんでした")
                if was_running:
                    self.engine.start()
                self.status.config(text="動作中" if was_running else "停止中",
                                   foreground="green" if was_running else "gray")
            self.after(0, ui)
        KeyCapture(done)

    def capture_combo(self, setter):
        self._capture(lambda keys: setter(keys_to_hotkey(keys)))

    def _insert_line(self, line):
        body = self.actions_text.get("1.0", "end").rstrip()
        self.actions_text.delete("1.0", "end")
        self.actions_text.insert("1.0", (body + "\n" if body else "") + line)

    def insert_func(self):
        choice = self.func_cb.get()
        if choice:
            self._insert_line(f"func: {CHOICES[choice][5:]}")

    def capture_hotkey(self):
        def apply(keys):
            self.hotkey_entry.delete(0, "end")
            self.hotkey_entry.insert(0, keys_to_hotkey(keys))
        self._capture(apply)

    # ---------- 共通 ----------
    def save(self):
        self.config_data = {
            "remaps": {str(v[0]): CHOICES.get(str(v[1]), str(v[1])) for v in
                       self.remap_tree.values()},
            "macros": self.macros,
        }
        CONFIG_PATH.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.engine.load(self.config_data)
        self.log("保存・反映しました")

    def _show_switch(self, on):
        color = "#2e9e4f" if on else "#9a9a9a"
        self.run_btn.config(text="ON" if on else "OFF", bg=color, activebackground=color,
                            activeforeground="white")

    def toggle(self):
        if self.engine.listener:
            self.engine.stop()
            self.status.config(text="停止中", foreground="gray")
        else:
            self.engine.start()
            self.status.config(text="動作中", foreground="green")
        self._show_switch(bool(self.engine.listener))

    def log(self, msg):
        def w():
            self.logbox.config(state="normal")
            self.logbox.insert("end", msg + "\n")
            self.logbox.see("end")
            self.logbox.config(state="disabled")
        self.after(0, w)

    def on_close(self):
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
