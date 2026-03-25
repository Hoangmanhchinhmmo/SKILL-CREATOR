"""
NPB Data Agent — Dynamic data enrichment via NotebookLM CLI.

Gọi trực tiếp lệnh `nlm` qua subprocess.
KHÔNG phụ thuộc project NoteBookLM_AUTO hay bất kỳ thư viện ngoài nào.

Yêu cầu duy nhất: user đã cài `nlm` CLI trên máy.
    pip install notebooklm-mcp-cli
    nlm login

Flow:
1. Kiểm tra nlm CLI có sẵn + đã auth
2. Tìm hoặc tạo notebook NPB
3. Dùng Research API tìm data mới từ keywords (do Gemini extract)
4. Query notebook lấy thông tin có cấu trúc
5. Trả về context cho pipeline
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys

log = logging.getLogger(__name__)

NPB_NOTEBOOK_NAME = "NPB Baseball Analysis"


# ─────────────────────────────────────────────
# Low-level CLI runner
# ─────────────────────────────────────────────

class NLMError(Exception):
    """Raised when an nlm CLI command fails."""


def _subprocess_env() -> dict[str, str]:
    """Env vars to fix Rich/Unicode crash on Windows."""
    env = os.environ.copy()
    if sys.platform == "win32":
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_COLOR"] = "1"
    return env


def _run_nlm(args: list[str], timeout: int = 30,
             json_output: bool = False) -> str | list | dict:
    """Run an `nlm` CLI command and return output.

    Args:
        args: Command args after `nlm`, e.g. ["notebook", "list"]
        timeout: Seconds before timeout
        json_output: Append --json flag and parse JSON response

    Returns:
        Parsed JSON (list/dict) if json_output=True, else raw stdout string.

    Raises:
        NLMError: If nlm is not found, times out, or exits non-zero.
    """
    cmd = ["nlm"] + args
    if json_output:
        cmd.append("--json")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=_subprocess_env(), encoding="utf-8",
        )
    except FileNotFoundError:
        raise NLMError("nlm CLI is not installed or not on PATH.")
    except subprocess.TimeoutExpired:
        raise NLMError(f"nlm timed out after {timeout}s: {' '.join(cmd)}")

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise NLMError(err or f"nlm exited with code {result.returncode}")

    stdout = result.stdout.strip()
    if json_output and stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return stdout
    return stdout


# ─────────────────────────────────────────────
# NLM API functions (standalone, no imports)
# ─────────────────────────────────────────────

def nlm_check_installed() -> bool:
    """Check if `nlm` CLI is on PATH."""
    return shutil.which("nlm") is not None


def nlm_check_auth() -> dict:
    """Check auth status. Returns dict with 'valid' key."""
    cmd = ["nlm", "login", "--check"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            env=_subprocess_env(), encoding="utf-8",
        )
    except FileNotFoundError:
        return {"valid": False, "error": "nlm not installed"}
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": "timeout"}

    text = (result.stdout + "\n" + result.stderr).strip()
    text_clean = re.sub(r"\[/?[a-z]+\]", "", text)

    info: dict = {"valid": False, "raw": text_clean}
    if result.returncode == 0 and ("valid" in text_clean.lower() or "✓" in text_clean):
        info["valid"] = True
    return info


def nlm_notebook_list() -> list[dict]:
    """List all notebooks. Returns list of {id, title, source_count}."""
    data = _run_nlm(["notebook", "list"], json_output=True)
    if isinstance(data, list):
        return [
            {
                "id": nb.get("id", ""),
                "title": nb.get("title", "Untitled"),
                "source_count": nb.get("source_count", nb.get("sourceCount", 0)),
            }
            for nb in data
        ]
    return []


def nlm_notebook_create(name: str) -> str:
    """Create a notebook, return its ID."""
    text = _run_nlm(["notebook", "create", name])
    m = re.search(r"([a-f0-9\-]{20,})", text, re.IGNORECASE)
    return m.group(1) if m else text


def nlm_notebook_query(notebook_id: str, question: str) -> str:
    """Query a notebook."""
    return _run_nlm(["notebook", "query", notebook_id, question], timeout=60)


def nlm_source_add(notebook_id: str, url: str) -> str:
    """Add a URL source to a notebook."""
    return _run_nlm(["source", "add", notebook_id, "--url", url], timeout=60)


def nlm_research_start(notebook_id: str, query: str,
                        source: str = "web", mode: str = "fast") -> str:
    """Start a web research query on a notebook."""
    return _run_nlm(
        ["research", "start", query,
         "--notebook-id", notebook_id,
         "--source", source, "--mode", mode, "--force"],
        timeout=60,
    )


def nlm_research_status(notebook_id: str, max_wait: int = 60) -> str:
    """Wait for research to complete and return results."""
    return _run_nlm(
        ["research", "status", notebook_id, "--max-wait", str(max_wait)],
        timeout=max_wait + 30,
    )


def nlm_research_import(notebook_id: str) -> str:
    """Import research results as notebook sources."""
    return _run_nlm(["research", "import", notebook_id], timeout=30)


# ─────────────────────────────────────────────
# High-level collector
# ─────────────────────────────────────────────

class NPBDataCollector:
    """Dynamic NPB data collection — calls `nlm` CLI directly.

    Zero external dependencies beyond the `nlm` executable on PATH.
    """

    def __init__(self):
        self._available = False
        self._notebook_id: str | None = None
        self._init()

    def _init(self):
        if not nlm_check_installed():
            log.info("NotebookLM: nlm CLI not installed — Gemini-only mode")
            return

        auth = nlm_check_auth()
        if not auth.get("valid"):
            log.warning("NotebookLM: auth invalid — run 'nlm login'")
            return

        self._available = True
        log.info("NotebookLM: ready")

    @property
    def available(self) -> bool:
        return self._available

    # --- Notebook ---

    def _find_notebook(self) -> str | None:
        try:
            notebooks = nlm_notebook_list()
            for nb in notebooks:
                title = nb.get("title", "").upper()
                if "NPB" in title or "野球" in nb.get("title", ""):
                    return nb["id"]
        except NLMError:
            pass
        return None

    def _get_or_create_notebook(self) -> str:
        if self._notebook_id:
            return self._notebook_id

        self._notebook_id = self._find_notebook()
        if not self._notebook_id:
            self._notebook_id = nlm_notebook_create(NPB_NOTEBOOK_NAME)
            log.info(f"NotebookLM: created notebook '{NPB_NOTEBOOK_NAME}'")

        return self._notebook_id

    # --- Research ---

    def research(self, keywords: list[str], max_wait: int = 30) -> list[str]:
        """Research each keyword via NotebookLM web search.
        Giới hạn 2 keywords để tránh treo quá lâu."""
        if not self._available:
            return []

        nb_id = self._get_or_create_notebook()
        results = []

        for kw in keywords[:2]:  # Tối đa 2 keywords
            try:
                nlm_research_start(nb_id, kw, source="web", mode="fast")
                result = nlm_research_status(nb_id, max_wait=max_wait)
                if result and "failed" not in result.lower():
                    results.append(result)
                try:
                    nlm_research_import(nb_id)
                except NLMError:
                    pass
            except NLMError as e:
                log.warning(f"NotebookLM: research failed for '{kw}' — {e}")

        return results

    # --- Query ---

    def query(self, question: str) -> str:
        if not self._available:
            return ""

        nb_id = self._get_or_create_notebook()
        try:
            return nlm_notebook_query(nb_id, question)
        except NLMError as e:
            log.warning(f"NotebookLM: query failed — {e}")
            return ""

    # --- Main entry ---

    def collect_match_data(self, user_input: str,
                           search_keywords: list[str] | None = None) -> str:
        """Collect match data dynamically.

        Args:
            user_input: Topic from user (e.g. "巨人 vs 阪神")
            search_keywords: Keywords extracted by Gemini for research.
        """
        if not self._available:
            return ""

        parts = []

        # Step 1: Research with extracted keywords
        if search_keywords:
            log.info(f"NotebookLM: researching {len(search_keywords)} keywords...")
            research_results = self.research(search_keywords)
            if research_results:
                parts.append("【最新リサーチ結果】\n" + "\n---\n".join(research_results))

        # Step 2: Query notebook for structured data
        structured_query = (
            f"{user_input} の試合プレビューに必要な情報をすべて教えてください。"
            f"先発投手、打線、救援陣、故障者、対戦成績、最近の調子を含めてください。"
        )
        query_result = self.query(structured_query)
        if query_result:
            parts.append(f"【NotebookLM分析】\n{query_result}")

        combined = "\n\n".join(parts)
        if combined:
            log.info(f"NotebookLM: collected {len(combined)} chars")
        else:
            log.info("NotebookLM: no data — Gemini-only mode")

        return combined


# ─────────────────────────────────────────────
# Public API — called from agents.py
# ─────────────────────────────────────────────

def collect_npb_data(user_input: str,
                     search_keywords: list[str] | None = None) -> str:
    """Convenience function for Agent 1.

    Args:
        user_input: Raw topic from user
        search_keywords: Keywords extracted by Gemini
    """
    collector = NPBDataCollector()
    return collector.collect_match_data(user_input, search_keywords)
