"""キーフック本体。キーの置き換え(リマップ)とマクロ実行を行う。"""
import os
import subprocess
import sys
import threading
import time

from pynput import keyboard
from pynput.keyboard import Controller, Key, KeyCode

from functions import combo_for
from keytables import MAC_KC, MOD_ALIASES, MODIFIERS, WIN_VK, normalize, parse_combo

IS_MAC = sys.platform == "darwin"
CODES = MAC_KC if IS_MAC else WIN_VK
NAMES = {v: k for k, v in CODES.items()}

PYNPUT_MOD = {"ctrl": Key.ctrl, "shift": Key.shift, "alt": Key.alt, "cmd": Key.cmd}
PYNPUT_SPECIAL = {
    "enter": Key.enter, "tab": Key.tab, "space": Key.space, "backspace": Key.backspace,
    "esc": Key.esc, "delete": Key.delete, "home": Key.home, "end": Key.end,
    "page_up": Key.page_up, "page_down": Key.page_down, "left": Key.left,
    "right": Key.right, "up": Key.up, "down": Key.down, "caps_lock": Key.caps_lock,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)},
}


def to_pynput(name):
    if name.startswith("@"):  # pynput の Key 名 (例: @media_volume_up)
        return getattr(Key, name[1:])
    if name in PYNPUT_MOD:
        return PYNPUT_MOD[name]
    if name in PYNPUT_SPECIAL:
        return PYNPUT_SPECIAL[name]
    if name in CODES:
        return KeyCode.from_vk(CODES[name])
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"不明なキー: {name}")


def output_action(dst):
    """キー変更の置き換え先 -> マクロのアクション"""
    if dst.startswith("func:"):
        return {"type": "func", "value": dst[5:]}
    return {"type": "combo", "value": dst}


class Engine:
    def __init__(self, config, log=print):
        self.log = log
        self.ctrl = Controller()
        self.listener = None
        self.held = set()          # 押下中の修飾キー(共通名: ctrl等)
        self.held_raw = set()      # 押下中の修飾キー(左右区別: ctrl_l等)
        self.busy = False
        self.swallow_up = set()    # 発動で握りつぶしたキー(離した時も握りつぶす)
        self.held_prefix = {}      # 押下中の前置キー(修飾キー以外) -> 使用済みか
        self.pass_mac = {}         # macOS: 自分で送り直すキーを素通しする回数
        self.load(config)

    # ---------- 設定 ----------
    def load(self, config):
        self.remaps, self.macros = {}, {}
        for src, dst in config.get("remaps", {}).items():
            try:
                if "+" not in src and src in CODES and dst in CODES:
                    self.remaps[CODES[src]] = CODES[dst]  # 単キー→単キーは押しっぱなしも効く置き換え
                else:
                    self.macros[parse_combo(src)] = {"hotkey": src, "actions": [output_action(dst)]}
            except ValueError as e:
                self.log(f"[警告] キー変更 {src}: {e}")
        for m in config.get("macros", []):
            try:
                self.macros[parse_combo(m["hotkey"])] = m
            except ValueError as e:
                self.log(f"[警告] {m.get('hotkey')}: {e}")
        # 'space+j' の space のような、修飾キー以外の前置キー
        self.prefix_keys = {CODES[k] for mods, _ in self.macros for k in mods
                            if k not in MODIFIERS and k in CODES}

    # ---------- 開始/停止 ----------
    def start(self):
        if self.listener:
            return
        kw = {"darwin_intercept": self._mac_filter} if IS_MAC else {"win32_event_filter": self._win_filter}
        self.listener = keyboard.Listener(**kw)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
            self.held.clear()
            self.held_raw.clear()
            self.held_prefix.clear()

    # ---------- 共通処理 ----------
    def _set_mod(self, name, down):
        if name not in MOD_ALIASES:
            return False
        (self.held_raw.add if down else self.held_raw.discard)(name)
        self.held = {MOD_ALIASES[n] for n in self.held_raw}
        return True

    def _handle(self, code, down):
        """戻り値: 'pass' / 'suppress' / ('remap', 新コード)"""
        name = NAMES.get(code)
        mod = self._set_mod(name, down)

        if not down and code in self.swallow_up:
            self.swallow_up.discard(code)
            return "suppress"

        # 前置キー: 押下中は握りつぶし、単独で離されたら本来のキーとして送る
        if code in self.prefix_keys:
            if down:
                self.held_prefix.setdefault(code, False)
                return "suppress"
            if code in self.held_prefix:
                if not self.held_prefix.pop(code):
                    self._tap_code(code)
                return "suppress"

        if down and name and not mod:
            held = self.held | {NAMES[c] for c in self.held_prefix}
            macro = self.macros.get((frozenset(held), name))
            if macro:
                for c in self.held_prefix:
                    self.held_prefix[c] = True
                self.swallow_up.add(code)
                threading.Thread(target=self._run_macro, args=(macro,), daemon=True).start()
                return "suppress"
            # マクロに無い組み合わせ → 前置キーを先に通常入力として送る(タイピング中の取りこぼし防止)
            for c, used in list(self.held_prefix.items()):
                if not used:
                    self._tap_code(c)
                    self.held_prefix[c] = True

        if code in self.remaps:
            return ("remap", self.remaps[code])
        return "pass"

    def _tap_code(self, code):
        if IS_MAC:
            self.pass_mac[code] = self.pass_mac.get(code, 0) + 2
        self.ctrl.tap(KeyCode.from_vk(code))

    # ---------- Windows ----------
    def _win_filter(self, msg, data):
        if data.flags & 0x10:  # LLKHF_INJECTED: 自分(や他ソフト)が送ったキーは素通し
            return
        down = msg in (0x0100, 0x0104)  # WM_KEYDOWN / WM_SYSKEYDOWN
        r = self._handle(data.vkCode, down)
        if r == "pass":
            return
        self.listener.suppress_event()  # 元のキーを握りつぶす
        if r != "suppress":
            k = KeyCode.from_vk(r[1])
            self.ctrl.press(k) if down else self.ctrl.release(k)

    # ---------- macOS ----------
    def _mac_filter(self, event_type, event):
        import Quartz as Q
        if self.busy:
            return event  # マクロ送信中のイベントは素通し
        code = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
        if event_type == Q.kCGEventFlagsChanged:
            name = NAMES.get(code)
            mod = MOD_ALIASES.get(name)
            if mod:
                flag = {"ctrl": Q.kCGEventFlagMaskControl, "shift": Q.kCGEventFlagMaskShift,
                        "alt": Q.kCGEventFlagMaskAlternate, "cmd": Q.kCGEventFlagMaskCommand}[mod]
                self._set_mod(name, bool(Q.CGEventGetFlags(event) & flag))
            return event  # 修飾キーのリマップはmacOS標準設定を推奨
        if event_type not in (Q.kCGEventKeyDown, Q.kCGEventKeyUp):
            return event
        if self.pass_mac.get(code):
            self.pass_mac[code] -= 1
            return event  # 前置キーの送り直し
        r = self._handle(code, event_type == Q.kCGEventKeyDown)
        if r == "pass":
            return event
        if r == "suppress":
            return None
        Q.CGEventSetIntegerValueField(event, Q.kCGKeyboardEventKeycode, r[1])
        return event

    # ---------- マクロ ----------
    def _run_macro(self, macro):
        self.log(f"実行: {macro['hotkey']}")
        self.busy = True
        # 押しっぱなしの修飾キー(例: shift+s の shift)が出力に混ざらないよう一旦離す
        held = [n for n in self.held_raw if n in CODES]
        for n in held:
            self.ctrl.release(KeyCode.from_vk(CODES[n]))
        try:
            for act in macro.get("actions", []):
                self._do(act)
        except Exception as e:
            self.log(f"[エラー] {e}")
        finally:
            # まだ押されている修飾キーは押し直す(続けて操作できるように)
            for n in held:
                if n in self.held_raw:
                    self.ctrl.press(KeyCode.from_vk(CODES[n]))
            self.busy = False

    def press_combo(self, combo):
        keys = [to_pynput(normalize(p)) for p in combo.split("+") if p.strip()]
        for k in keys:
            self.ctrl.press(k)
        for k in reversed(keys):
            self.ctrl.release(k)

    def _do(self, act):
        kind, val = act["type"], str(act.get("value", ""))
        if kind == "text":
            self.ctrl.type(val)
        elif kind == "wait":
            time.sleep(float(val))
        elif kind in ("key", "combo"):
            self.press_combo(val)
        elif kind == "func":
            self.press_combo(combo_for(val))
        elif kind == "open":
            if IS_MAC:
                subprocess.Popen(["open", val])
            else:
                os.startfile(val)
        else:
            raise ValueError(f"不明なアクション: {kind}")
        time.sleep(0.01)
