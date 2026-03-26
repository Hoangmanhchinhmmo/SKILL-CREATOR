"""
Pipeline Runner — Background thread wrapper for pipeline_v2.
Emits progress events via callback for real-time UI updates.
"""

import sys
import os
import re
import threading
import datetime
import time

from db.models import (
    create_article, create_pipeline_run, update_pipeline_run,
    create_agent_log, update_agent_log, get_setting,
)
from services.machine_id import get_machine_code
from services.crypto import decrypt

# Add Skill-bong-chay to path — search multiple locations for packaged builds
_app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_candidates = [
    # flet pack (onedir): Skill-bong-chay/ next to exe in same folder
    os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "Skill-bong-chay"),
    # flet pack (onefile): PyInstaller temp dir
    os.path.join(getattr(sys, "_MEIPASS", ""), "Skill-bong-chay"),
    # Development: ../Skill-bong-chay relative to project root
    os.path.join(_app_root, "..", "Skill-bong-chay"),
    # flet build windows: app/Skill-bong-chay
    os.path.join(_app_root, "Skill-bong-chay"),
]
SKILL_DIR = ""
for _c in _candidates:
    _c = os.path.abspath(_c)
    if os.path.isdir(_c):
        SKILL_DIR = _c
        break
if not SKILL_DIR:
    SKILL_DIR = os.path.abspath(os.path.join(_app_root, "..", "Skill-bong-chay"))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)


def _inject_settings_to_env():
    """Read encrypted API keys and settings from SQLite, inject into os.environ
    so the existing pipeline code picks them up via config.py's load_dotenv/getenv.
    """
    mc = get_machine_code()

    key_map = {
        "gemini_key_writer": "GEMINI_API_KEY_WRITER",
        "gemini_key_editor": "GEMINI_API_KEY_EDITOR",
        "gemini_key_architect": "GEMINI_API_KEY_ARCHITECT",
    }
    for db_key, env_key in key_map.items():
        val = get_setting(db_key)
        if val:
            decrypted = decrypt(val, mc)
            if decrypted:
                os.environ[env_key] = decrypted

    # 9Router settings
    router_url = get_setting("router_url")
    if router_url:
        os.environ["ROUTER_URL"] = router_url
    elif "ROUTER_URL" in os.environ:
        del os.environ["ROUTER_URL"]

    router_api_key = get_setting("router_api_key")
    if router_api_key:
        mc = get_machine_code()
        decrypted_key = decrypt(router_api_key, mc)
        if decrypted_key:
            os.environ["ROUTER_API_KEY"] = decrypted_key
    elif "ROUTER_API_KEY" in os.environ:
        del os.environ["ROUTER_API_KEY"]

    setting_map = {
        "model_data": "GEMINI_MODEL_DATA",
        "model_analysis": "GEMINI_MODEL_ANALYSIS",
        "model_writer": "GEMINI_MODEL_WRITER",
        "model_supervisor": "GEMINI_MODEL_SUPERVISOR",
        "temperature": "TEMPERATURE",
        "supervisor_temperature": "SUPERVISOR_TEMPERATURE",
        "max_output_tokens": "MAX_OUTPUT_TOKENS",
        "max_retries": "MAX_RETRIES",
    }
    for db_key, env_key in setting_map.items():
        val = get_setting(db_key)
        if val:
            os.environ[env_key] = val


def _post_process(text: str) -> str:
    """メタ応答と連続（間）を除去する。"""
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
    text = re.sub(r"(（間）\s*\n?\s*){2,}", "（間）\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.lstrip("\n")
    return text


# Agent definitions for v2 pipeline
# Title Generation is appended to ALL pipelines automatically
_TITLE_AGENT = {"name": "Title Generation", "key": "title_gen"}

V2_AGENTS = [
    {"name": "Data Collection", "key": "data_collector"},
    {"name": "Tactical Analysis", "key": "tactical_analyst"},
    {"name": "Opening (HCRP)", "key": "opening"},
    {"name": "Pitching Analysis", "key": "pitching"},
    {"name": "Batting Analysis", "key": "batting"},
    {"name": "Bullpen & Defense", "key": "bullpen"},
    {"name": "Unique Perspective", "key": "perspective"},
    {"name": "Prediction & Ending", "key": "prediction"},
    {"name": "Post-processing", "key": "postprocess"},
    _TITLE_AGENT,
]

V1_AGENTS = [
    {"name": "Data Collection", "key": "data_collector"},
    {"name": "Tactical Analysis", "key": "tactical_analyst"},
    {"name": "Unique Perspective", "key": "unique_perspective"},
    {"name": "Script Writer", "key": "script_writer"},
    {"name": "Quality Checker", "key": "quality_checker"},
    _TITLE_AGENT,
]

V3_AGENTS = [
    {"name": "Research", "key": "v3_research"},
    {"name": "Outline", "key": "v3_outline"},
    {"name": "Writing", "key": "v3_writing"},
    _TITLE_AGENT,
]


class PipelineRunner:
    """Runs the NPB pipeline in a background thread with progress callbacks."""

    def __init__(self, on_progress=None, on_complete=None, on_error=None, on_log=None):
        """
        Callbacks:
            on_progress(agent_name, status, attempt, message)
            on_complete(article_id, run_id)
            on_error(message)
            on_log(timestamp, agent, message)
        """
        self.on_progress = on_progress or (lambda *a: None)
        self.on_complete = on_complete or (lambda *a: None)
        self.on_error = on_error or (lambda *a: None)
        self.on_log = on_log or (lambda *a: None)
        self._thread = None
        self._cancelled = False
        self.run_id = None
        self.article_id = None

    def start(self, topic: str, format_type: str, pipeline_version: str = "v2"):
        """Start pipeline in background thread."""
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run, args=(topic, format_type, pipeline_version), daemon=True,
        )
        self._thread.start()

    def cancel(self):
        """Request cancellation (best effort)."""
        self._cancelled = True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, agent: str, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.on_log(ts, agent, message)

    def _run(self, topic: str, format_type: str, pipeline_version: str):
        """Main pipeline execution (runs in thread)."""
        start_time = time.time()

        # Inject settings into env
        _inject_settings_to_env()

        # Create pipeline run record
        self.run_id = create_pipeline_run()

        if pipeline_version == "v3":
            agents = V3_AGENTS
        elif pipeline_version == "v2":
            agents = V2_AGENTS
        else:
            agents = V1_AGENTS

        # Create agent log entries
        agent_log_ids = {}
        for agent in agents:
            log_id = create_agent_log(self.run_id, agent["name"])
            agent_log_ids[agent["key"]] = log_id
            self.on_progress(agent["name"], "waiting", 0, "")

        try:
            if pipeline_version == "v3":
                result = self._run_v3(topic, format_type, agents, agent_log_ids)
            elif pipeline_version == "v2":
                result = self._run_v2(topic, format_type, agents, agent_log_ids)
            else:
                result = self._run_v1(topic, agents, agent_log_ids)

            if self._cancelled:
                self._finish_run("cancelled", start_time)
                self.on_error("Pipeline đã bị hủy")
                return

            # Title Generation (shared across all pipelines)
            titles_json = ""
            if result and "title_gen" in agent_log_ids:
                try:
                    titles_json = self._generate_titles(result, agent_log_ids["title_gen"])
                except Exception as e:
                    self._log("Title Gen", f"Failed (non-fatal): {e}")

            # Save article
            self.article_id = create_article(topic, format_type, result)
            if titles_json:
                from db.models import update_article_titles
                update_article_titles(self.article_id, titles_json)
            update_pipeline_run(self.run_id, article_id=self.article_id)
            self._finish_run("completed", start_time)
            self.on_complete(self.article_id, self.run_id)

        except Exception as e:
            self._finish_run("failed", start_time)
            self.on_error(f"Pipeline lỗi: {str(e)}")

    def _run_v2(self, topic: str, format_type: str, agents: list, log_ids: dict) -> str:
        """Execute v2 pipeline with section-by-section progress tracking."""
        # Reimport to get fresh config after env injection
        import importlib
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        if "agents" in sys.modules:
            importlib.reload(sys.modules["agents"])
        if "section_writers" in sys.modules:
            importlib.reload(sys.modules["section_writers"])
        if "supervisor" in sys.modules:
            importlib.reload(sys.modules["supervisor"])

        from agents import agent_data_collector, agent_tactical_analyst
        from section_writers import (
            write_opening, write_pitching_analysis, write_batting_analysis,
            write_bullpen_defense, write_unique_perspective, write_prediction_ending,
        )
        from supervisor import review_section
        from config import MAX_RETRIES

        # Phase 0: Data Collection
        self._run_agent("Data Collection", log_ids["data_collector"], lambda: agent_data_collector(topic))
        if self._cancelled:
            return ""
        data = self._last_result

        self._run_agent("Tactical Analysis", log_ids["tactical_analyst"], lambda: agent_tactical_analyst(data))
        if self._cancelled:
            return ""
        analysis = self._last_result

        context = f"{topic}\n\n{data}"

        # Phase 1: Sections with review
        section_writers = [
            ("Opening (HCRP)", "opening", "オープニング", lambda: write_opening(context)),
            ("Pitching Analysis", "pitching", "先発投手比較", lambda: write_pitching_analysis(data, analysis)),
            ("Batting Analysis", "batting", "打線比較", lambda: write_batting_analysis(data, analysis)),
            ("Bullpen & Defense", "bullpen", "救援陣・守備", lambda: write_bullpen_defense(data, analysis)),
            ("Unique Perspective", "perspective", "独自の視点", lambda: write_unique_perspective(data, analysis)),
        ]

        sections = []
        for display_name, key, section_name, writer_func in section_writers:
            if self._cancelled:
                return ""
            text = self._run_agent_with_review(
                display_name, log_ids[key], writer_func, section_name, review_section, MAX_RETRIES,
            )
            sections.append(text)

        # Prediction needs s5 (unique perspective)
        if self._cancelled:
            return ""
        s5 = sections[-1] if sections else ""
        text = self._run_agent_with_review(
            "Prediction & Ending", log_ids["prediction"],
            lambda: write_prediction_ending(data, analysis, s5),
            "予測・締め", review_section, MAX_RETRIES,
        )
        sections.append(text)

        # Phase 2: Assemble
        self.on_progress("Post-processing", "running", 1, "Assembling...")
        update_agent_log(log_ids["postprocess"], status="running", started_at=datetime.datetime.now().isoformat())
        self._log("Post-process", "Assembling sections + cleanup")

        full_script = "\n\n（間）\n\n".join(sections)

        # Post-process (inline — không phụ thuộc pipeline_v2.py)
        full_script = _post_process(full_script)

        update_agent_log(log_ids["postprocess"], status="passed", finished_at=datetime.datetime.now().isoformat())
        self.on_progress("Post-processing", "passed", 1, "Done")
        self._log("Post-process", "✅ Done")

        return full_script

    def _run_v1(self, topic: str, agents: list, log_ids: dict) -> str:
        """Execute v1 pipeline."""
        import importlib
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        if "agents" in sys.modules:
            importlib.reload(sys.modules["agents"])

        from agents import (
            agent_data_collector, agent_tactical_analyst,
            agent_unique_perspective, agent_script_writer, agent_quality_checker,
        )
        from config import FORMATS, DEFAULT_FORMAT

        # Detect format
        format_type = DEFAULT_FORMAT
        for keyword, fmt in FORMATS.items():
            if keyword in topic:
                format_type = fmt
                break

        data = self._run_agent("Data Collection", log_ids["data_collector"], lambda: agent_data_collector(topic))
        if self._cancelled:
            return ""
        data = self._last_result

        self._run_agent("Tactical Analysis", log_ids["tactical_analyst"], lambda: agent_tactical_analyst(data))
        if self._cancelled:
            return ""
        analysis = self._last_result

        self._run_agent("Unique Perspective", log_ids["unique_perspective"], lambda: agent_unique_perspective(data, analysis))
        if self._cancelled:
            return ""
        perspective = self._last_result

        self._run_agent("Script Writer", log_ids["script_writer"], lambda: agent_script_writer(data, analysis, perspective, format_type))
        if self._cancelled:
            return ""
        script = self._last_result

        self._run_agent("Quality Checker", log_ids["quality_checker"], lambda: agent_quality_checker(script))
        if self._cancelled:
            return ""

        return self._last_result

    def _run_v3(self, topic: str, format_type: str, agents: list, log_ids: dict) -> str:
        """Execute v3 pipeline — multi-agent script generation.
        format_type is JSON string with v3 params: style, hook, language, duration, channel.

        Flow: Research → Outline → Writing (chunked) → Editing → Post-processing
        Does NOT touch v1/v2 code paths."""
        import importlib
        import json

        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        if "agents" in sys.modules:
            importlib.reload(sys.modules["agents"])
        if "writing_styles" in sys.modules:
            importlib.reload(sys.modules["writing_styles"])

        from agents import _call_gemini
        from writing_styles import (
            build_script_prompt, SYSTEM_INSTRUCTION, SCRIPT_STYLES,
            STORYTELLING_VI, STORYTELLING_EN,
        )

        # Parse v3 params
        try:
            params = json.loads(format_type)
        except (json.JSONDecodeError, TypeError):
            params = {}

        style = params.get("style", "baseball_jp")
        hook = params.get("hook", "dramatic")
        language = params.get("language", "ja")
        duration = params.get("duration", 23)
        channel = params.get("channel", "")
        style_name = SCRIPT_STYLES.get(style, "Kể chuyện")
        is_vi = language == "vi"

        self._log("V3", f"Style={style_name}, Lang={language}, Hook={hook}, Duration={duration}min")

        # ── Agent 1: Research ──
        self._run_agent("Research", log_ids["v3_research"], lambda: self._v3_research(topic, _call_gemini))
        if self._cancelled:
            return ""
        research_data = self._last_result

        # ── Agent 2: Outline ──
        self._run_agent("Outline", log_ids["v3_outline"], lambda: self._v3_outline(
            topic, research_data, style_name, language, duration, hook, is_vi, _call_gemini,
        ))
        if self._cancelled:
            return ""
        outline = self._last_result

        # ── Agent 3: Writing (chunked by outline sections) ──
        self._run_agent("Writing", log_ids["v3_writing"], lambda: self._v3_write(
            topic, outline, research_data, style, language, duration, channel, is_vi, _call_gemini,
        ))
        if self._cancelled:
            return ""
        return self._last_result

    # ── V3 Agent implementations ──

    def _v3_research(self, topic: str, call_fn) -> str:
        """Agent 1: Research — thu thập dữ liệu về topic qua AI."""
        prompt = f"""以下のトピックについて、記事を書くために必要な背景情報、データ、重要ポイントを調査してまとめてください。

トピック: {topic}

【出力ルール】
- 箇条書きで簡潔にまとめる
- 具体的な数字、名前、日付を含める
- 情報が不明な場合は「不明」と書く
- 500〜1000文字程度"""

        result = call_fn(
            "あなたはリサーチャーです。トピックについて正確な情報を収集します。",
            prompt, "data_collector",
        )
        return result if result else f"トピック: {topic}"

    def _v3_outline(self, topic: str, research: str, style_name: str,
                     language: str, duration: int, hook: str, is_vi: bool, call_fn) -> str:
        """Agent 2: Outline — tạo dàn ý chi tiết."""
        from writing_styles import SYSTEM_INSTRUCTION
        if is_vi:
            prompt = f"""Tạo dàn ý chi tiết cho bài viết {duration} phút về: "{topic}"

Phong cách: {style_name}
Hook mở đầu: {hook}

【Dữ liệu tham khảo】
{research[:2000]}

【Yêu cầu dàn ý】
- Chia thành 4-6 phần chính
- Mỗi phần ghi rõ: tiêu đề, nội dung chính (3-5 gạch đầu dòng), thời lượng ước tính
- Phần 1 phải là Hook + giới thiệu
- Phần cuối phải là kết luận + CTA
- Tổng thời lượng = {duration} phút
- Chỉ trả về dàn ý, không viết bài"""
        else:
            prompt = f"""Create a detailed outline for a {duration}-minute script about: "{topic}"

Style: {style_name}
Opening hook: {hook}
Language: {language}

【Reference data】
{research[:2000]}

【Outline requirements】
- Split into 4-6 main sections
- Each section: title, key points (3-5 bullets), estimated duration
- Section 1 must be Hook + introduction
- Final section must be conclusion + CTA
- Total duration = {duration} minutes
- Return ONLY the outline, do not write the script"""

        return call_fn(SYSTEM_INSTRUCTION, prompt, "tactical_analyst")

    def _v3_write(self, topic: str, outline: str, research: str,
                   style: str, language: str, duration: int, channel: str,
                   is_vi: bool, call_fn) -> str:
        """Agent 3: Writing — viết script theo dàn ý.
        Chia chunks nếu duration > 10 phút (giống logic index.html gốc).
        Mỗi chunk nhận: partSummary từ outline + 300 ký tự cuối chunk trước."""
        from writing_styles import SYSTEM_INSTRUCTION
        import re

        CHUNK_MINUTES = 10

        if duration <= CHUNK_MINUTES:
            # Short script — single call, dùng full outline
            return self._v3_write_single(
                topic, outline, research, style, language, duration, channel, is_vi, call_fn,
            )

        # --- Long script: theo đúng logic index.html ---
        num_chunks = -(-duration // CHUNK_MINUTES)

        # Parse outline thành list partSummary
        outline_parts = [
            line.strip() for line in outline.split("\n")
            if re.match(r"^\d+[\.\)]\s*", line.strip())
        ]
        self._log("Writing", f"{duration}min -> {num_chunks} chunks, {len(outline_parts)} outline parts")

        script_parts = []
        for i in range(num_chunks):
            is_first = (i == 0)
            is_last = (i == num_chunks - 1)
            chunk_dur = CHUNK_MINUTES if not is_last else max(1, duration - CHUNK_MINUTES * (num_chunks - 1))

            # partSummary từ outline
            part_summary = outline_parts[i] if i < len(outline_parts) else (
                "Tiếp tục câu chuyện một cách logic từ phần trước." if is_vi
                else "Logically continue the story from the previous part."
            )

            # Context từ chunk trước (300 ký tự cuối)
            prev_context = ""
            if i > 0 and script_parts[i - 1]:
                tail = script_parts[i - 1][-300:]
                prev_context = (
                    f'Bối cảnh: Phần trước của kịch bản đã kết thúc như sau: "...{tail}".'
                    if is_vi
                    else f'Context: The previous part of the script ended like this: "...{tail}".'
                )

            # Storytelling techniques cho chunk
            if is_vi:
                chunk_techniques = (
                    "\nHÃY NHỚ CÁC NGUYÊN TẮC KỂ CHUYỆN: Vì đây là phần cuối, hãy giải quyết xung đột chính, đóng lại Vòng Lặp Mở, và đưa ra một kết luận đanh thép."
                    if is_last else
                    "\nHÃY NHỚ CÁC NGUYÊN TẮC KỂ CHUYỆN: Duy trì sự tò mò, phát triển xung đột, đi sâu vào cảm xúc, và có thể lồng ghép các chi tiết dữ liệu hoặc trích dẫn để tăng sức nặng."
                )
            else:
                chunk_techniques = (
                    "\nREMEMBER STORYTELLING PRINCIPLES: As this is the final part, you MUST resolve the main conflict, close the Open Loop, and deliver a powerful conclusion."
                    if is_last else
                    "\nREMEMBER STORYTELLING PRINCIPLES: Maintain suspense, escalate the conflict, delve into emotions, and consider weaving in data or quotes to add weight."
                )

            # CTA cho chunk đầu và cuối
            chunk_cta = ""
            if channel:
                if is_vi:
                    if is_first:
                        chunk_cta = f'\nYÊU CẦU MỞ ĐẦU: Hãy viết một đoạn mở đầu thật hấp dẫn. Ngay sau đó, viết lời chào mừng sáng tạo đến kênh "{channel}" liên quan đến chủ đề.'
                    if is_last:
                        chunk_cta += f'\nYÊU CẦU KẾT THÚC: Ở cuối, viết CTA kêu gọi thích, chia sẻ, đăng ký kênh "{channel}", và đặt câu hỏi mở.'
                else:
                    if is_first:
                        chunk_cta = f'\nOPENING: Write an engaging opening. Then welcome viewers to "{channel}" channel.'
                    if is_last:
                        chunk_cta += f'\nCONCLUDING: End with CTA for likes, shares, subscribes to "{channel}", and an open question.'

            # Build chunk prompt (giống index.html)
            self._log("Writing", f"Chunk {i+1}/{num_chunks} ({chunk_dur}min)")
            self.on_progress("Writing", "running", 1, f"Chunk {i+1}/{num_chunks}")

            if is_vi:
                chunk_prompt = (
                    f'Bây giờ, hãy viết chi tiết phần kịch bản cho một phần của câu chuyện lớn hơn.\n'
                    f'- Ý tưởng tổng thể là: "{topic}"\n'
                    f'- {prev_context}\n'
                    f'- Hướng đi cho phần này là về: "{part_summary}"\n'
                    f'Yêu cầu: Viết một đoạn văn xuôi liền mạch, dài khoảng {chunk_dur} phút đọc. '
                    f'{chunk_cta}{chunk_techniques}'
                )
            else:
                chunk_prompt = (
                    f'Now, write a detailed script section for a part of a larger story, IN {language}.\n'
                    f'- The overall idea (in Vietnamese) is: "{topic}"\n'
                    f'- {prev_context}\n'
                    f'- The guideline for this part is: "{part_summary}"\n'
                    f'Requirement: Write a seamless prose passage of about {chunk_dur} minutes reading time. '
                    f'{chunk_cta}{chunk_techniques}'
                )

            chunk_text = call_fn(SYSTEM_INSTRUCTION, chunk_prompt, "script_writer")
            script_parts.append(chunk_text.strip() if chunk_text else "")

        return "\n\n".join(p for p in script_parts if p)

    def _v3_write_single(self, topic, outline, research, style, language,
                          duration, channel, is_vi, call_fn) -> str:
        """Write short script (<=10 min) in a single call."""
        from writing_styles import build_script_prompt

        system_instruction, style_prompt = build_script_prompt(
            idea=topic, style=style, language=language,
            duration=duration, hook_type="", channel_name=channel,
        )

        if is_vi:
            prompt = f"""{style_prompt}

【DÀN Ý — TUÂN THEO】
{outline}

【DỮ LIỆU THAM KHẢO】
{research[:2000]}

【QUAN TRỌNG】
- Viết liền mạch, không có tiêu đề hay đánh dấu phần
- Thời lượng đọc: {duration} phút"""
        else:
            prompt = f"""{style_prompt}

【OUTLINE — FOLLOW】
{outline}

【REFERENCE DATA】
{research[:2000]}

【IMPORTANT】
- Write as seamless prose, no section headers
- Reading duration: {duration} minutes"""

        return call_fn(system_instruction, prompt, "script_writer")

    def _generate_titles(self, script: str, log_id: int) -> str:
        """Generate 3-5 title suggestions from script content. Shared by all pipelines."""
        import json as _json
        import importlib

        if "title_generator" in sys.modules:
            importlib.reload(sys.modules["title_generator"])
        if "agents" in sys.modules:
            importlib.reload(sys.modules["agents"])

        from title_generator import build_title_prompt, parse_titles
        from agents import _call_gemini

        self.on_progress("Title Generation", "running", 1, "Generating titles...")
        update_agent_log(log_id, status="running", attempt=1,
                         started_at=datetime.datetime.now().isoformat())
        self._log("Title Gen", "Generating 5 title suggestions...")

        system_inst, prompt = build_title_prompt(script)
        raw = _call_gemini(system_inst, prompt, "quality_checker")
        titles = parse_titles(raw) if raw else []

        if titles:
            self._log("Title Gen", f"Generated {len(titles)} titles")
            for i, t in enumerate(titles, 1):
                self._log("Title Gen", f"  {i}. {t}")
        else:
            self._log("Title Gen", "No titles parsed")

        update_agent_log(log_id, status="passed",
                         finished_at=datetime.datetime.now().isoformat())
        self.on_progress("Title Generation", "passed", 1, f"{len(titles)} titles")

        return _json.dumps(titles, ensure_ascii=False)

    def _run_agent(self, display_name: str, log_id: int, func, attempt: int = 1):
        """Run a single agent, track progress."""
        self.on_progress(display_name, "running", attempt, "")
        update_agent_log(log_id, status="running", attempt=attempt, started_at=datetime.datetime.now().isoformat())
        self._log(display_name, f"Start (attempt {attempt})")

        try:
            self._last_result = func()
            update_agent_log(log_id, status="passed", finished_at=datetime.datetime.now().isoformat())
            self.on_progress(display_name, "passed", attempt, "")
            self._log(display_name, "✅ Done")
        except Exception as e:
            update_agent_log(log_id, status="failed", finished_at=datetime.datetime.now().isoformat(), error_msg=str(e))
            self.on_progress(display_name, "failed", attempt, str(e))
            self._log(display_name, f"❌ Error: {e}")
            raise

    def _run_agent_with_review(self, display_name: str, log_id: int, writer_func,
                                section_name: str, review_func, max_retries: int) -> str:
        """Run a section writer with supervisor review loop."""
        self.on_progress(display_name, "running", 1, "Writing...")
        update_agent_log(log_id, status="running", attempt=1, started_at=datetime.datetime.now().isoformat())
        self._log(display_name, "Start writing")

        text = writer_func()

        for attempt in range(max_retries + 1):
            if self._cancelled:
                return text

            self._log(display_name, f"Supervisor reviewing (attempt {attempt + 1})")
            result = review_func(text, section_name)

            if result["passed"]:
                update_agent_log(log_id, status="passed", attempt=attempt + 1, finished_at=datetime.datetime.now().isoformat())
                self.on_progress(display_name, "passed", attempt + 1, "")
                self._log(display_name, f"✅ Passed (attempt {attempt + 1})")
                return result["text"]

            if attempt < max_retries:
                reason = result.get("reason", "Unknown")
                self.on_progress(display_name, "retrying", attempt + 2, f"Retry — {reason}")
                update_agent_log(log_id, status="retrying", attempt=attempt + 2, error_msg=reason)
                self._log(display_name, f"⟳ Retry: {reason}")
                text = writer_func()  # Rewrite

        # Max retries exhausted, use what we have
        update_agent_log(log_id, status="passed", finished_at=datetime.datetime.now().isoformat())
        self.on_progress(display_name, "passed", max_retries + 1, "Max retries reached")
        self._log(display_name, f"✅ Accepted after max retries")
        return text

    def _finish_run(self, status: str, start_time: float):
        """Finalize pipeline run record."""
        total = time.time() - start_time
        now = datetime.datetime.now().isoformat()
        update_pipeline_run(self.run_id, status=status, finished_at=now, total_time=total)
