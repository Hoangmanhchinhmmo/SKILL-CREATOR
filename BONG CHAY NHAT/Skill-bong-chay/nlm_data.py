"""
NPB Data Agent — Lấy dữ liệu thực từ NotebookLM qua nlm CLI.

Flow:
1. Query notebook NPB để lấy thông tin trận đấu
2. Nếu notebook chưa có → tạo mới + thêm sources
3. Trả về context data cho pipeline
"""

import sys
import os

# Thêm path đến NoteBookLM_AUTO để import NLMClient
NLM_PROJECT = os.path.join("d:", os.sep, "CODE_2026", "NoteBookLM_AUTO")
if NLM_PROJECT not in sys.path:
    sys.path.insert(0, NLM_PROJECT)

from core.nlm_cli import NLMClient, NLMError


# === Config ===
NPB_NOTEBOOK_NAME = "NPB Baseball Analysis"
NPB_SOURCES = [
    "https://npb.jp/",
    "https://baseballking.jp/",
    "https://news.yahoo.co.jp/categories/sports",
    "https://www.nikkansports.com/baseball/professional/",
    "https://full-count.jp/",
]


class NPBDataCollector:
    """Thu thập dữ liệu NPB từ NotebookLM."""

    def __init__(self):
        self.nlm = NLMClient()
        self._notebook_id = None

    def _find_notebook(self) -> str | None:
        """Tìm notebook NPB đã tồn tại."""
        try:
            notebooks = self.nlm.notebook_list()
            for nb in notebooks:
                if "NPB" in nb.title.upper() or "野球" in nb.title:
                    return nb.id
        except NLMError:
            pass
        return None

    def _create_notebook(self) -> str:
        """Tạo notebook NPB mới và thêm sources."""
        nb_id = self.nlm.notebook_create(NPB_NOTEBOOK_NAME)

        for url in NPB_SOURCES:
            try:
                self.nlm.source_add(nb_id, url=url)
            except NLMError:
                pass  # Bỏ qua nếu source lỗi

        return nb_id

    def get_notebook_id(self) -> str:
        """Lấy hoặc tạo notebook NPB."""
        if self._notebook_id:
            return self._notebook_id

        self._notebook_id = self._find_notebook()
        if not self._notebook_id:
            self._notebook_id = self._create_notebook()

        return self._notebook_id

    def query(self, question: str) -> str:
        """Query NotebookLM để lấy thông tin NPB."""
        nb_id = self.get_notebook_id()
        try:
            return self.nlm.notebook_query(nb_id, question)
        except NLMError as e:
            return f"NotebookLM query failed: {e}"

    def research(self, topic: str) -> str:
        """Dùng NotebookLM Research để tìm thông tin mới nhất."""
        nb_id = self.get_notebook_id()
        try:
            self.nlm.research_start(nb_id, topic, source="web", mode="fast")
            result = self.nlm.research_status(nb_id, max_wait=60)
            # Auto-import kết quả research
            try:
                self.nlm.research_import(nb_id)
            except NLMError:
                pass
            return result
        except NLMError as e:
            return f"Research failed: {e}"

    def collect_match_data(self, user_input: str) -> str:
        """Thu thập toàn bộ dữ liệu cho 1 trận đấu.

        Gửi 1 query tổng hợp đến NotebookLM,
        trả về context data cho pipeline.
        """
        try:
            result = self.query(
                f"{user_input} の試合プレビューに必要な情報をすべて教えてください。"
                f"先発投手、打線、救援陣、故障者、対戦成績、最近の調子を含めてください。"
            )
            if result and "failed" not in result.lower():
                return result
        except Exception:
            pass

        return ""


def collect_npb_data(user_input: str) -> str:
    """便利関数 — Agent 1から呼び出す用."""
    collector = NPBDataCollector()
    return collector.collect_match_data(user_input)
