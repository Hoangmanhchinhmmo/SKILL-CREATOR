"""
NPB Podcast Multi-Agent System — Configuration
Sử dụng Gemini API để tạo script podcast bóng chày Nhật Bản
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === Gemini API Keys (3 keys xoay vòng giữa các agent) ===
GEMINI_API_KEY_WRITER = os.getenv("GEMINI_API_KEY_WRITER", "")
GEMINI_API_KEY_EDITOR = os.getenv("GEMINI_API_KEY_EDITOR", "")
GEMINI_API_KEY_ARCHITECT = os.getenv("GEMINI_API_KEY_ARCHITECT", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# Phân bổ key cho từng agent:
# WRITER    → Agent 1 (データ収集), Agent 4 (台本作成)
# EDITOR    → Agent 2 (戦術分析), Agent 5 (品質検査)
# ARCHITECT → Agent 3 (独自視点)
AGENT_KEYS = {
    "data_collector": GEMINI_API_KEY_WRITER,
    "tactical_analyst": GEMINI_API_KEY_EDITOR,
    "unique_perspective": GEMINI_API_KEY_ARCHITECT,
    "script_writer": GEMINI_API_KEY_WRITER,
    "quality_checker": GEMINI_API_KEY_EDITOR,
}

# === Output ===
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Agent Settings ===
MAX_RETRIES = 2
TEMPERATURE = 0.8  # Sáng tạo hơn cho podcast
MAX_OUTPUT_TOKENS = 16384

# === Podcast Formats ===
FORMATS = {
    "プレビュー": "試合プレビュー",
    "予告": "試合プレビュー",
    "まとめ": "週間まとめ",
    "週間": "週間まとめ",
    "ランキング": "パワーランキング",
    "チーム分析": "チーム深掘り分析",
    "選手": "選手スポットライト",
    "スポットライト": "選手スポットライト",
    "戦術": "戦術ブレイクダウン",
    "プレーオフ": "ポストシーズン予測",
    "日本シリーズ": "ポストシーズン予測",
    "初心者": "初心者向け解説",
    "ルール": "初心者向け解説",
}
DEFAULT_FORMAT = "試合プレビュー"

# === TTS Quality Rules ===
TTS_RULES = """
- 1文は40文字以内
- 読点「、」を適切に入れる
- 漢字の連続は4文字まで
- 段落間に（間）を入れる
- 英語は一切使用禁止
- 日本人名はひらがな
- 外国人名はカタカナ
- 数字はアラビア数字
"""
