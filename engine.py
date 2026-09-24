"""キーフック本体。キーの置き換え(リマップ)とマクロ実行を行う。"""
import sys
import threading
import time

from pynput import keyboard
from pynput.keyboard import Controller, Key, KeyCode

from keytables import MAC_KC, MOD_ALIASES, MODIFIERS, WIN_VK, parse_combo

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
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
    if name in PYNPUT_MOD:
        return PYNPUT_MOD[name]
    if name in PYNPUT_SPECIAL:
        return PYNPUT_SPECIAL[name]
    if name in CODES:
        return KeyCode.from_vk(CODES[name])
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"不明なキー: {name}")


class Engine:
    def __init__(self, config, log=print):
        self.log = log
        self.ctrl = Controller()
        self.listener = None
        self.held = set()          # 押下中の修飾キー(共通名)
        self.busy = False
        self.swallow_up = set()    # マクロ発動で握りつぶしたキー(離した時も握りつぶす)
        self.load(config)

    # ---------- 設定 ----------
    def load(self, config):
        self.remaps = {}
        for src, dst in config.get("remaps", {}).items():
            if src in CODES and dst in CODES:
                self.remaps[CODES[src]] = CODES[dst]
            else:
                self.log(f"[警告] このOSでは使えないリマップ: {src} -> {dst}")
        self.macros = {}
        for m in config.get("macros", []):
            try:
                self.macros[parse_combo(m["hotkey"])] = m
            except ValueError as e:
                self.log(f"[警告] {m.get('hotkey')}: {e}")

    # ---------- 開始/停止 ----------
    def start(self):
        if self.listener:
            return
        kw = {"darwin_intercept": self._mac_filter} if IS_MAC else {"win32_event_filter": self._win_filter}
        self.listener = keyboard.Listener(**kw)
        self.listener.start()
        self.log("フック開始")

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
            self.held.clear()
            self.log("フック停止")

    # ---------- 共通処理 ----------
    def _handle(self, code, down):
        """戻り値: 'pass' / 'suppress' / ('remap', 新コード)"""
        name = NAMES.get(code)
        mod = MOD_ALIASES.get(name)
        if mod:
            (self.held.add if down else self.held.discard)(mod)

        if not down and code in self.swallow_up:
            self.swallow_up.discard(code)
            return "suppress"

        if down and name and not mod:
            macro = self.macros.get((frozenset(self.held), name))
            if macro:
                self.swallow_up.add(code)
                threading.Thread(target=self._run_macro, args=(macro,), daemon=True).start()
                return "suppress"

        if code in self.remaps:
            return ("remap", self.remaps[code])
        return "pass"

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
        code = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
        if event_type == Q.kCGEventFlagsChanged:
            name = NAMES.get(code)
            mod = MOD_ALIASES.get(name)
            if mod:
                flag = {"ctrl": Q.kCGEventFlagMaskControl, "shift": Q.kCGEventFlagMaskShift,
                        "alt": Q.kCGEventFlagMaskAlternate, "cmd": Q.kCGEventFlagMaskCommand}[mod]
                down = bool(Q.CGEventGetFlags(event) & flag)
                (self.held.add if down else self.held.discard)(mod)
            return event  # 修飾キーのリマップはmacOS標準設定を推奨
        if event_type not in (Q.kCGEventKeyDown, Q.kCGEventKeyUp):
            return event
        if self.busy:
            return event  # マクロ送信中のイベントは素通し
        r = self._handle(code, event_type == Q.kCGEventKeyDown)
        if r == "pass":
            return event
        if r == "suppress":
            return None
        Q.CGEventSetIntegerValueField(event, Q.kCGKeyboardEventKeycode, r[1])
        return event

    # ---------- マクロ ----------
    def _run_macro(self, macro):
        self.log(f"マクロ実行: {macro['hotkey']}")
        # 押しっぱなしの修飾キーが混ざらないよう、離されるまで最大2秒待つ
        t = time.time()
        while self.held and time.time() - t < 2:
            time.sleep(0.02)
        self.busy = True
        try:
            for act in macro.get("actions", []):
                self._do(act)
        except Exception as e:
            self.log(f"[エラー] マクロ失敗: {e}")
        finally:
            self.busy = False

    def _do(self, act):
        kind, val = act["type"], act.get("value", "")
        if kind == "text":
            self.ctrl.type(str(val))
        elif kind == "wait":
            time.sleep(float(val))
        elif kind in ("key", "combo"):
            mods, key = parse_combo(str(val))
            with self.ctrl.pressed(*[PYNPUT_MOD[m] for m in mods]):
                self.ctrl.tap(to_pynput(key))
        else:
            raise ValueError(f"不明なアクション: {kind}")
        time.sleep(0.01)
