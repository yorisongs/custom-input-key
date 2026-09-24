"""キーやマクロに割り当てられる便利機能。 値: (表示名, Windows用, macOS用)
Windows用/macOS用 は 'ctrl+c' 形式のキー組み合わせ、または pynput の Key 名 ('@media_volume_up')。
None はそのOSでは未対応。"""
import sys

FUNCTIONS = {
    "screenshot_area": ("スクリーンショット(範囲)", "cmd+shift+s", "cmd+shift+4"),
    "screenshot_full": ("スクリーンショット(全画面)", "@print_screen", "cmd+shift+3"),
    "screenshot_window": ("スクリーンショット(ウィンドウ)", "alt+@print_screen", "cmd+shift+4+space"),
    "copy": ("コピー", "ctrl+c", "cmd+c"),
    "paste": ("貼り付け", "ctrl+v", "cmd+v"),
    "cut": ("切り取り", "ctrl+x", "cmd+x"),
    "undo": ("元に戻す", "ctrl+z", "cmd+z"),
    "redo": ("やり直し", "ctrl+y", "cmd+shift+z"),
    "select_all": ("すべて選択", "ctrl+a", "cmd+a"),
    "save": ("保存", "ctrl+s", "cmd+s"),
    "find": ("検索", "ctrl+f", "cmd+f"),
    "new_tab": ("新しいタブ", "ctrl+t", "cmd+t"),
    "close_tab": ("タブを閉じる", "ctrl+w", "cmd+w"),
    "close_window": ("ウィンドウを閉じる", "alt+f4", "cmd+q"),
    "switch_window": ("ウィンドウ切り替え", "alt+tab", "cmd+tab"),
    "show_desktop": ("デスクトップ表示", "cmd+d", None),
    "lock_screen": ("画面ロック", "cmd+l", "ctrl+cmd+q"),
    "task_manager": ("タスクマネージャー / 強制終了", "ctrl+shift+esc", "cmd+alt+esc"),
    "volume_up": ("音量を上げる", "@media_volume_up", "@media_volume_up"),
    "volume_down": ("音量を下げる", "@media_volume_down", "@media_volume_down"),
    "volume_mute": ("ミュート", "@media_volume_mute", "@media_volume_mute"),
    "play_pause": ("再生/一時停止", "@media_play_pause", "@media_play_pause"),
    "next_track": ("次の曲", "@media_next", "@media_next"),
    "prev_track": ("前の曲", "@media_previous", "@media_previous"),
}


def combo_for(name):
    if name not in FUNCTIONS:
        raise ValueError(f"不明な機能: {name}")
    combo = FUNCTIONS[name][2 if sys.platform == "darwin" else 1]
    if combo is None:
        raise ValueError(f"このOSでは未対応の機能: {FUNCTIONS[name][0]}")
    return combo


def label(name):
    return FUNCTIONS[name][0] if name in FUNCTIONS else name


# GUIの選択肢用 "📌 表示名" <-> "func:名前"
CHOICES = {f"📌 {v[0]}": f"func:{k}" for k, v in FUNCTIONS.items()}
CHOICE_OF = {v: k for k, v in CHOICES.items()}
