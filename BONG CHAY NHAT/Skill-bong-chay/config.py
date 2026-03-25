"""
NPB Podcast Multi-Agent System — Configuration
Sử dụng Gemini API để tạo script podcast bóng chày Nhật Bản
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === 9Router (route qua local 9router thay vì gọi trực tiếp Gemini) ===
_raw_router_url = os.getenv("ROUTER_URL", "http://localhost:20128").rstrip("/")
# Strip trailing /v1 nếu user nhập URL kèm /v1
if _raw_router_url.endswith("/v1"):
    _raw_router_url = _raw_router_url[:-3]
ROUTER_URL = _raw_router_url  # e.g. http://localhost:20128
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")  # API key cho 9router

# === Gemini API Keys (3 keys xoay vòng giữa các agent) ===
GEMINI_API_KEY_WRITER = os.getenv("GEMINI_API_KEY_WRITER", "")
GEMINI_API_KEY_EDITOR = os.getenv("GEMINI_API_KEY_EDITOR", "")
GEMINI_API_KEY_ARCHITECT = os.getenv("GEMINI_API_KEY_ARCHITECT", "")

# === Gemini Model per step (cấu hình từ .env) ===
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_MODEL_DATA = os.getenv("GEMINI_MODEL_DATA", GEMINI_MODEL)
GEMINI_MODEL_ANALYSIS = os.getenv("GEMINI_MODEL_ANALYSIS", GEMINI_MODEL)
GEMINI_MODEL_WRITER = os.getenv("GEMINI_MODEL_WRITER", GEMINI_MODEL)
GEMINI_MODEL_SUPERVISOR = os.getenv("GEMINI_MODEL_SUPERVISOR", GEMINI_MODEL)

# Phân bổ key + model cho từng agent
AGENT_KEYS = {
    "data_collector": GEMINI_API_KEY_WRITER,
    "tactical_analyst": GEMINI_API_KEY_EDITOR,
    "unique_perspective": GEMINI_API_KEY_ARCHITECT,
    "script_writer": GEMINI_API_KEY_WRITER,
    "quality_checker": GEMINI_API_KEY_EDITOR,
}

AGENT_MODELS = {
    "data_collector": GEMINI_MODEL_DATA,
    "tactical_analyst": GEMINI_MODEL_ANALYSIS,
    "unique_perspective": GEMINI_MODEL_ANALYSIS,
    "script_writer": GEMINI_MODEL_WRITER,
    "quality_checker": GEMINI_MODEL_SUPERVISOR,
}

# === Output ===
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === Agent Settings (cấu hình từ .env) ===
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))
SUPERVISOR_TEMPERATURE = float(os.getenv("SUPERVISOR_TEMPERATURE", "0.3"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "16384"))

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
