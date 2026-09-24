# ダブルクリックで黒い画面なし・トレイ常駐で起動するランチャー
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().with_name("src")))  # 本体は src/ にまとめてある

from app import main

main()
