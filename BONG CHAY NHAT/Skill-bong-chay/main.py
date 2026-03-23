"""
NPB Podcast Multi-Agent System — Main Pipeline
使い方: python main.py "はんしん vs よみうり"
"""

import sys
import os
import io
import datetime

# Fix Windows console encoding for Japanese output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import FORMATS, DEFAULT_FORMAT, OUTPUT_DIR, AGENT_KEYS
from agents import (
    agent_data_collector,
    agent_tactical_analyst,
    agent_unique_perspective,
    agent_script_writer,
    agent_quality_checker,
)


def detect_format(user_input: str) -> str:
    """ユーザー入力からポッドキャストフォーマットを自動検出"""
    for keyword, format_name in FORMATS.items():
        if keyword in user_input:
            return format_name
    return DEFAULT_FORMAT


def run_pipeline(user_input: str) -> str:
    """5エージェントパイプラインを実行"""

    format_type = detect_format(user_input)

    # === Agent 1 ===
    data = agent_data_collector(user_input)

    # === Agent 2 ===
    analysis = agent_tactical_analyst(data)

    # === Agent 3 ===
    perspective = agent_unique_perspective(data, analysis)

    # === Agent 4 ===
    script = agent_script_writer(data, analysis, perspective, format_type)

    # === Agent 5 ===
    final_script = agent_quality_checker(script)

    return final_script


def save_output(script: str, user_input: str) -> str:
    """台本をファイルに保存"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = user_input[:30].replace(" ", "_").replace("/", "_")
    filename = f"{timestamp}_{safe_name}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        f.write(script)

    return filepath


def main():
    # API key チェック
    missing = [k for k, v in AGENT_KEYS.items() if not v]
    if missing:
        print("エラー: 以下のAPI Keyが .env に設定されていません:")
        for m in missing:
            print(f"  - {m}")
        print("\n.env ファイルに以下を設定してください:")
        print("  GEMINI_API_KEY_WRITER=...")
        print("  GEMINI_API_KEY_EDITOR=...")
        print("  GEMINI_API_KEY_ARCHITECT=...")
        sys.exit(1)

    # ユーザー入力
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("Topic: ").strip()
        if not user_input:
            sys.exit(0)

    # パイプライン実行
    final_script = run_pipeline(user_input)

    # 保存
    filepath = save_output(final_script, user_input)


if __name__ == "__main__":
    main()
