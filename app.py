"""Custom Input Key - キーリマップ & マクロ設定GUI"""
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from engine import Engine
from keytables import ALL_KEYS, parse_combo

CONFIG_PATH = Path(__file__).with_name("config.json")
DEFAULT = {
    "remaps": {"caps_lock": "ctrl_l"},
    "macros": [
        {"hotkey": "ctrl+alt+m", "actions": [
            {"type": "text", "value": "よろしくお願いします。"},
            {"type": "key", "value": "enter"}]},
    ],
}
HELP = "1行に1アクション:\n  text: 入力する文字\n  key: enter\n  combo: ctrl+c\n  wait: 0.5 (秒)"


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
        if not sep or kind not in ("text", "key", "combo", "wait"):
            raise ValueError(f"{n}行目の形式が不正です: {line}")
        val = val[1:] if val.startswith(" ") else val
        if kind in ("key", "combo"):
            parse_combo(val)
        elif kind == "wait":
            float(val)
        acts.append({"type": kind, "value": val})
    return acts


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Custom Input Key")
        self.geometry("640x520")
        self.config_data = load_config()
        self.engine = Engine(self.config_data, log=self.log)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        self.run_btn = ttk.Button(top, text="▶ 開始", command=self.toggle)
        self.run_btn.pack(side="left")
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
        self.remap_tree = ttk.Treeview(f, columns=("src", "dst"), show="headings", height=10)
        self.remap_tree.heading("src", text="押したキー")
        self.remap_tree.heading("dst", text="→ 置き換え後")
        self.remap_tree.pack(fill="both", expand=True)
        for s, d in self.config_data.get("remaps", {}).items():
            self.remap_tree.insert("", "end", values=(s, d))
        row = ttk.Frame(f)
        row.pack(fill="x", pady=6)
        self.src_cb = ttk.Combobox(row, values=ALL_KEYS, width=14)
        self.dst_cb = ttk.Combobox(row, values=ALL_KEYS, width=14)
        self.src_cb.pack(side="left")
        ttk.Label(row, text="→").pack(side="left", padx=4)
        self.dst_cb.pack(side="left")
        ttk.Button(row, text="追加", command=self.add_remap).pack(side="left", padx=6)
        ttk.Button(row, text="選択を削除",
                   command=lambda: [self.remap_tree.delete(i) for i in self.remap_tree.selection()]
                   ).pack(side="left")
        return f

    def add_remap(self):
        s, d = self.src_cb.get().strip(), self.dst_cb.get().strip()
        if s not in ALL_KEYS or d not in ALL_KEYS:
            messagebox.showerror("エラー", "一覧にあるキー名を選んでください")
            return
        for i in self.remap_tree.get_children():
            if self.remap_tree.item(i)["values"][0] == s:
                self.remap_tree.delete(i)
        self.remap_tree.insert("", "end", values=(s, d))

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
        ttk.Label(right, text="ホットキー (例: ctrl+alt+m / cmd+shift+1)").pack(anchor="w")
        self.hotkey_entry = ttk.Entry(right)
        self.hotkey_entry.pack(fill="x")
        ttk.Label(right, text=HELP, foreground="gray").pack(anchor="w", pady=4)
        self.actions_text = tk.Text(right, height=10)
        self.actions_text.pack(fill="both", expand=True)
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

    # ---------- 共通 ----------
    def save(self):
        self.config_data = {
            "remaps": {str(v[0]): str(v[1]) for v in
                       (self.remap_tree.item(i)["values"] for i in self.remap_tree.get_children())},
            "macros": self.macros,
        }
        CONFIG_PATH.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.engine.load(self.config_data)
        self.log("保存・反映しました")

    def toggle(self):
        if self.engine.listener:
            self.engine.stop()
            self.run_btn.config(text="▶ 開始")
            self.status.config(text="停止中", foreground="gray")
        else:
            self.engine.start()
            self.run_btn.config(text="■ 停止")
            self.status.config(text="動作中", foreground="green")

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
