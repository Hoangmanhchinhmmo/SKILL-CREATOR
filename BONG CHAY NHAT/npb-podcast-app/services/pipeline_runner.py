"""
Pipeline Runner — Background thread wrapper for pipeline_v2.
Emits progress events via callback for real-time UI updates.
"""

import sys
import os
import threading
import datetime
import time

from db.models import (
    create_article, create_pipeline_run, update_pipeline_run,
    create_agent_log, update_agent_log, get_setting,
)
from services.machine_id import get_machine_code
from services.crypto import decrypt

# Add Skill-bong-chay to path
SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "Skill-bong-chay")
SKILL_DIR = os.path.abspath(SKILL_DIR)
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


# Agent definitions for v2 pipeline
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
]

V1_AGENTS = [
    {"name": "Data Collection", "key": "data_collector"},
    {"name": "Tactical Analysis", "key": "tactical_analyst"},
    {"name": "Unique Perspective", "key": "unique_perspective"},
    {"name": "Script Writer", "key": "script_writer"},
    {"name": "Quality Checker", "key": "quality_checker"},
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

        agents = V2_AGENTS if pipeline_version == "v2" else V1_AGENTS

        # Create agent log entries
        agent_log_ids = {}
        for agent in agents:
            log_id = create_agent_log(self.run_id, agent["name"])
            agent_log_ids[agent["key"]] = log_id
            self.on_progress(agent["name"], "waiting", 0, "")

        try:
            if pipeline_version == "v2":
                result = self._run_v2(topic, format_type, agents, agent_log_ids)
            else:
                result = self._run_v1(topic, agents, agent_log_ids)

            if self._cancelled:
                self._finish_run("cancelled", start_time)
                self.on_error("Pipeline đã bị hủy")
                return

            # Save article
            self.article_id = create_article(topic, format_type, result)
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

        # Post-process
        from pipeline_v2 import post_process
        full_script = post_process(full_script)

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
