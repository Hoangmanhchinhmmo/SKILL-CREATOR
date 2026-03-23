"""
NPB Podcast Multi-Agent Pipeline v2 — Write-Review Loop
使い方: python pipeline_v2.py "広島 vs 中日 開幕戦"

Architecture:
  NLM Data → [Section Writer → Supervisor Review → Retry?] × 6 → Assemble → Output

Each section is written by a specialized agent, then reviewed by Supervisor.
If FAIL → rewrite with feedback (max 2 retries).
If PASS → move to next section.
"""

import sys
import os
import io
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import FORMATS, DEFAULT_FORMAT, OUTPUT_DIR, AGENT_KEYS, MAX_RETRIES
from agents import agent_data_collector, agent_tactical_analyst
from section_writers import (
    write_opening,
    write_pitching_analysis,
    write_batting_analysis,
    write_bullpen_defense,
    write_unique_perspective,
    write_prediction_ending,
)
from supervisor import review_section


def detect_format(user_input: str) -> str:
    for keyword, format_name in FORMATS.items():
        if keyword in user_input:
            return format_name
    return DEFAULT_FORMAT


def write_with_review(writer_func, section_name: str, *args) -> str:
    """Write a section, review it, retry if needed."""
    text = writer_func(*args)

    for attempt in range(MAX_RETRIES + 1):
        result = review_section(text, section_name)

        if result["passed"]:
            return result["text"]

        if attempt < MAX_RETRIES:
            # Rewrite with feedback
            feedback_prompt = (
                f"前回の「{section_name}」セクションが不合格でした。\n"
                f"理由：{result['reason']}\n"
                f"改善指示：{result['instruction']}\n\n"
                f"以下を改善して書き直してください：\n{text}"
            )
            text = writer_func(*args)  # Retry

    # After max retries, return whatever we have
    return text


def run_pipeline_v2(user_input: str) -> str:
    """6-section pipeline with Supervisor review loop."""

    # === Phase 0: Data Collection ===
    data = agent_data_collector(user_input)
    analysis = agent_tactical_analyst(data)

    # === Phase 1: Write each section with review ===
    context = f"{user_input}\n\n{data}"

    sections = []

    # Section 1: Opening (HCRP)
    s1 = write_with_review(write_opening, "オープニング", context)
    sections.append(s1)

    # Section 2: Pitching Analysis
    s2 = write_with_review(write_pitching_analysis, "先発投手比較", data, analysis)
    sections.append(s2)

    # Section 3: Batting Analysis
    s3 = write_with_review(write_batting_analysis, "打線比較", data, analysis)
    sections.append(s3)

    # Section 4: Bullpen + Defense
    s4 = write_with_review(write_bullpen_defense, "救援陣・守備", data, analysis)
    sections.append(s4)

    # Section 5: Unique Perspective
    s5 = write_with_review(write_unique_perspective, "独自の視点", data, analysis)
    sections.append(s5)

    # Section 6: Prediction + Ending
    s6 = write_with_review(write_prediction_ending, "予測・締め", data, analysis, s5)
    sections.append(s6)

    # === Phase 2: Assemble ===
    full_script = "\n\n（間）\n\n".join(sections)

    # === Phase 3: Post-processing (最終防衛ライン) ===
    full_script = post_process(full_script)

    return full_script


def post_process(text: str) -> str:
    """機械的にメタ応答と連続（間）を除去する。"""
    import re

    # 1. メタ応答を削除
    meta_patterns = [
        r"^はい、承知いたしました。?\n?",
        r"^了解しました。?\n?",
        r"^承知しました。?\n?",
        r"^以下の通りです。?\n?",
        r"^ご指定の内容を.*?\n",
        r"^ご質問にお答えします。?\n?",
        r"^NPBの.*?専門家として.*?\n",
    ]
    for pattern in meta_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE)

    # 2. 連続（間）を1つに統合
    text = re.sub(r"(（間）\s*\n?\s*){2,}", "（間）\n", text)

    # 3. 空行の連続を2行まで
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # 4. 先頭の空行を削除
    text = text.lstrip("\n")

    return text


def save_output(script: str, user_input: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = user_input[:30].replace(" ", "_").replace("/", "_")
    filename = f"v2_{timestamp}_{safe_name}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        f.write(script)
    return filepath


def main():
    missing = [k for k, v in AGENT_KEYS.items() if not v]
    if missing:
        print("Error: Missing API keys in .env")
        sys.exit(1)

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("Topic: ").strip()
        if not user_input:
            sys.exit(0)

    final_script = run_pipeline_v2(user_input)
    filepath = save_output(final_script, user_input)


if __name__ == "__main__":
    main()
