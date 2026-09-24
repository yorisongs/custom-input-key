"""キー名 <-> OS固有キーコード の対応表 (Windows: 仮想キーコード / macOS: CGKeyCode)"""

MODIFIERS = {"ctrl", "shift", "alt", "cmd"}

# 左右のある修飾キーを共通名にまとめる
MOD_ALIASES = {
    "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift_l": "shift", "shift_r": "shift",
    "alt_l": "alt", "alt_r": "alt",
    "cmd_l": "cmd", "cmd_r": "cmd",
}

WIN_VK = {
    **{chr(c).lower(): c for c in range(0x41, 0x5B)},   # a-z
    **{str(d): 0x30 + d for d in range(10)},            # 0-9
    **{f"f{i}": 0x6F + i for i in range(1, 13)},        # f1-f12
    "enter": 0x0D, "tab": 0x09, "space": 0x20, "backspace": 0x08, "esc": 0x1B,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "page_up": 0x21, "page_down": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "caps_lock": 0x14, "minus": 0xBD, "equal": 0xBB,
    "shift_l": 0xA0, "shift_r": 0xA1, "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "alt_l": 0xA4, "alt_r": 0xA5, "cmd_l": 0x5B, "cmd_r": 0x5C,
    # 日本語キーボード
    "muhenkan": 0x1D, "henkan": 0x1C, "kana": 0x15, "hankaku_zenkaku": 0xF3,
}

MAC_KC = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "equal": 24, "9": 25,
    "7": 26, "minus": 27, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "enter": 36, "tab": 48, "space": 49, "backspace": 51, "esc": 53,
    "cmd_r": 54, "cmd_l": 55, "shift_l": 56, "caps_lock": 57, "alt_l": 58,
    "ctrl_l": 59, "shift_r": 60, "alt_r": 61, "ctrl_r": 62,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "delete": 117, "home": 115, "end": 119, "page_up": 116, "page_down": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    # 日本語キーボード
    "eisu": 102, "kana": 104,
}

ALL_KEYS = sorted(set(WIN_VK) | set(MAC_KC))


def normalize(name: str) -> str:
    name = name.strip().lower()
    return {"control": "ctrl", "option": "alt", "win": "cmd", "command": "cmd",
            "return": "enter", "escape": "esc"}.get(name, name)


def parse_combo(text: str):
    """'ctrl+alt+m' -> (frozenset({'ctrl','alt'}), 'm')
    修飾キー以外も前置できる: 'space+j' -> (frozenset({'space'}), 'j') = スペース押しながらJ"""
    parts = [normalize(p) for p in text.split("+") if p.strip()]
    if not parts:
        raise ValueError("空のキー指定です")
    mods = frozenset(MOD_ALIASES.get(p, p) for p in parts[:-1])
    bad = {m for m in mods | {parts[-1]} if m not in MODIFIERS and m not in ALL_KEYS and len(m) != 1}
    if bad:
        raise ValueError(f"不明なキー: {', '.join(bad)}")
    return mods, parts[-1]
