"""
Pipeline Tab — Real-time progress display with agent cards and log panel.
Uses page.run_thread() for thread-safe UI updates from background pipeline.
"""

import time
import threading
import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, WARNING, DANGER, INFO,
    card_style, accent_button, danger_button, status_badge,
)
from services.pipeline_runner import PipelineRunner, V2_AGENTS, V1_AGENTS, V3_AGENTS

STATUS_ICONS = {
    "waiting": ("⏳", TEXT_MUTED),
    "running": ("⟳", INFO),
    "passed": ("✅", SUCCESS),
    "failed": ("❌", DANGER),
    "retrying": ("⟳", WARNING),
}


class PipelineTab(ft.Column):
    """Pipeline real-time progress view."""

    def __init__(self, page: ft.Page, on_open_editor=None):
        super().__init__(expand=True, spacing=12)
        self._page = page
        self.on_open_editor = on_open_editor
        self.runner: PipelineRunner | None = None
        self._start_time = 0
        self._timer_running = False
        self._timer_thread: threading.Thread | None = None

        # UI elements
        self._topic = ""
        self.title_text = ft.Text("Pipeline", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)
        self.copy_title_btn = ft.IconButton(
            icon=ft.Icons.COPY_ROUNDED, icon_size=18, tooltip="Copy title",
            on_click=self._on_copy_title, icon_color=TEXT_MUTED,
        )
        self.copy_title_btn.visible = False
        self.status_text = ft.Text("Chờ lệnh...", size=14, color=TEXT_MUTED)
        self.timer_text = ft.Text("00:00", size=14, color=TEXT_MUTED)

        self.agent_cards_column = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        self.log_panel = ft.ListView(spacing=2, height=200, auto_scroll=True)
        self.log_container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Agent Log", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                ]),
                self.log_panel,
            ], spacing=4),
            **card_style(),
            height=220,
        )

        self.cancel_btn = danger_button("HỦY", icon=ft.Icons.STOP_ROUNDED, on_click=self._on_cancel)
        self.cancel_btn.visible = False

        self.open_editor_btn = accent_button(
            "Hoàn tất → Mở Editor", icon=ft.Icons.EDIT_ROUNDED, on_click=self._on_open_editor,
        )
        self.open_editor_btn.visible = False

        self.controls = [
            ft.Row([self.title_text, self.copy_title_btn, ft.Container(expand=True), self.status_text, self.timer_text], spacing=12),
            self.agent_cards_column,
            self.log_container,
            ft.Row([self.cancel_btn, ft.Container(expand=True), self.open_editor_btn], spacing=12),
        ]

        # Agent card refs
        self._agent_cards: dict[str, ft.Container] = {}
        self._agent_status_icons: dict[str, ft.Text] = {}
        self._agent_status_texts: dict[str, ft.Text] = {}
        self._agent_time_texts: dict[str, ft.Text] = {}
        self._agent_attempt_texts: dict[str, ft.Text] = {}
        self._agent_msg_texts: dict[str, ft.Text] = {}
        self._agent_progress_bars: dict[str, ft.ProgressBar] = {}
        self._agent_start_times: dict[str, float] = {}

    def _safe_update(self):
        """Thread-safe page update."""
        try:
            self._page.update()
        except Exception:
            pass

    def start(self, topic: str, format_type: str, pipeline_version: str, app_state: dict):
        """Start a pipeline run."""
        self._topic = topic
        self.title_text.value = f"Pipeline — {topic[:50]}"
        self.copy_title_btn.visible = True
        self.status_text.value = "Đang chạy"
        self.status_text.color = INFO
        self.cancel_btn.visible = True
        self.open_editor_btn.visible = False

        # Clear previous state
        self.agent_cards_column.controls.clear()
        self.log_panel.controls.clear()
        self._agent_cards.clear()
        self._agent_start_times.clear()

        # Build agent cards
        if pipeline_version == "v3":
            agents = V3_AGENTS
        elif pipeline_version == "v2":
            agents = V2_AGENTS
        else:
            agents = V1_AGENTS
        for agent in agents:
            self._build_agent_card(agent["name"])

        self._page.update()

        # Start live timer
        self._start_time = time.time()
        self._timer_running = True
        self._start_timer_loop()

        # Create runner with thread-safe callbacks
        self.runner = PipelineRunner(
            on_progress=lambda *a: self._page.run_thread(self._on_progress, *a),
            on_complete=lambda aid, rid: self._page.run_thread(self._on_complete, aid, rid, app_state),
            on_error=lambda msg: self._page.run_thread(self._on_error, msg),
            on_log=lambda *a: self._page.run_thread(self._on_log, *a),
        )
        self.runner.start(topic, format_type, pipeline_version)

    def _start_timer_loop(self):
        """Start a background thread that updates the timer every second."""
        def _tick():
            while self._timer_running:
                elapsed = time.time() - self._start_time
                m = int(elapsed // 60)
                s = int(elapsed % 60)
                self.timer_text.value = f"{m:02d}:{s:02d}"
                self._safe_update()
                time.sleep(1)

        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def _build_agent_card(self, agent_name: str):
        """Build a progress card for one agent."""
        icon = ft.Text("⏳", size=18)
        status = ft.Text("Waiting", size=12, color=TEXT_MUTED)
        time_text = ft.Text("—", size=12, color=TEXT_MUTED, width=50)
        attempt_text = ft.Text("", size=11, color=TEXT_MUTED, width=40)
        msg_text = ft.Text("", size=11, color=TEXT_MUTED)
        progress = ft.ProgressBar(visible=False, color=ACCENT, bgcolor=BORDER, height=3)

        card = ft.Container(
            content=ft.Column([
                ft.Row([
                    icon,
                    ft.Text(agent_name, size=13, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600, expand=True),
                    time_text,
                    attempt_text,
                    status,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                progress,
                msg_text,
            ], spacing=4),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            bgcolor=BG_CARD,
            border=ft.border.all(1, BORDER),
            border_radius=6,
        )

        self._agent_cards[agent_name] = card
        self._agent_status_icons[agent_name] = icon
        self._agent_status_texts[agent_name] = status
        self._agent_time_texts[agent_name] = time_text
        self._agent_attempt_texts[agent_name] = attempt_text
        self._agent_msg_texts[agent_name] = msg_text
        self._agent_progress_bars[agent_name] = progress

        self.agent_cards_column.controls.append(card)

    def _on_progress(self, agent_name: str, status: str, attempt: int, message: str):
        """Callback from PipelineRunner — update agent card. Runs on main thread via run_thread."""
        if agent_name not in self._agent_cards:
            return

        icon_char, color = STATUS_ICONS.get(status, ("⏳", TEXT_MUTED))
        self._agent_status_icons[agent_name].value = icon_char
        self._agent_status_texts[agent_name].value = status.capitalize()
        self._agent_status_texts[agent_name].color = color

        if attempt > 0:
            max_a = 3  # MAX_RETRIES + 1
            self._agent_attempt_texts[agent_name].value = f"[{attempt}/{max_a}]"

        if message:
            self._agent_msg_texts[agent_name].value = message
            self._agent_msg_texts[agent_name].color = WARNING if status == "retrying" else TEXT_MUTED

        # Progress bar
        progress = self._agent_progress_bars[agent_name]
        if status == "running":
            progress.visible = True
            progress.value = None  # Indeterminate
            if agent_name not in self._agent_start_times:
                self._agent_start_times[agent_name] = time.time()
        else:
            progress.visible = False

        # Update time for completed agents
        if status in ("passed", "failed") and agent_name in self._agent_start_times:
            elapsed = time.time() - self._agent_start_times[agent_name]
            m = int(elapsed // 60)
            s = int(elapsed % 60)
            self._agent_time_texts[agent_name].value = f"{m:02d}:{s:02d}"

        # Update card border color
        border_map = {"passed": SUCCESS, "failed": DANGER, "running": INFO, "retrying": WARNING}
        if status in border_map:
            self._agent_cards[agent_name].border = ft.border.all(1, border_map[status])

        self._safe_update()

    def _on_complete(self, article_id: int, run_id: int, app_state: dict):
        """Pipeline completed successfully. Runs on main thread."""
        self._timer_running = False
        self.status_text.value = "Hoàn tất!"
        self.status_text.color = SUCCESS
        self.cancel_btn.visible = False
        self.open_editor_btn.visible = True
        app_state["current_article_id"] = article_id
        app_state["current_run_id"] = run_id

        elapsed = time.time() - self._start_time
        m = int(elapsed // 60)
        s = int(elapsed % 60)
        self.timer_text.value = f"{m:02d}:{s:02d}"

        self._on_log(self.timer_text.value, "Pipeline", f"✅ Hoàn tất ({m}m {s}s)")
        self._safe_update()

    def _on_error(self, message: str):
        """Pipeline error. Runs on main thread."""
        self._timer_running = False
        self.status_text.value = "Lỗi"
        self.status_text.color = DANGER
        self.cancel_btn.visible = False

        self._on_log("", "Pipeline", f"❌ {message}")
        self._safe_update()

    def _on_log(self, timestamp: str, agent: str, message: str):
        """Add a log entry to the log panel. Runs on main thread."""
        color = TEXT_SECONDARY
        if "✅" in message:
            color = SUCCESS
        elif "❌" in message:
            color = DANGER
        elif "⟳" in message:
            color = WARNING

        self.log_panel.controls.append(
            ft.Text(f"  {timestamp}  [{agent}] {message}", size=11, color=color),
        )
        self._safe_update()

    def _on_copy_title(self, e):
        """Copy topic title to clipboard."""
        if self._topic:
            self._page.run_task(ft.Clipboard().set, self._topic)
            show_snackbar(self._page, "Đã copy title", 1500)

    def _on_cancel(self, e):
        """Cancel button clicked."""
        def on_confirm(e):
            close_dialog(self._page, dialog)
            if self.runner:
                self.runner.cancel()
            self._timer_running = False
            self.status_text.value = "Đã hủy"
            self.status_text.color = WARNING
            self.cancel_btn.visible = False
            self._page.update()

        def on_dismiss(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Hủy pipeline?"),
            content=ft.Text("Pipeline đang chạy sẽ bị dừng."),
            actions=[
                ft.TextButton(content=ft.Text("Tiếp tục"), on_click=on_dismiss),
                ft.TextButton(content=ft.Text("Hủy pipeline"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _on_open_editor(self, e):
        """Open editor with completed article."""
        if self.runner and self.runner.article_id and self.on_open_editor:
            self.on_open_editor(self.runner.article_id)
