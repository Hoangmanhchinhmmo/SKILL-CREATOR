"""
Tab Progress — Review segment splits + pipeline progress + real-time preview.
"""

import json
import threading
import time

import flet as ft
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT,
    SUCCESS, DANGER, INFO, WARNING,
    card_style, accent_button, outlined_button, danger_button, show_snackbar,
    status_badge, CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)


class TabProgress(ft.Column):
    """Progress sub-tab — segment review + pipeline execution + preview."""

    def __init__(self, page: ft.Page, state, on_complete=None):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self._state = state
        self._on_complete = on_complete
        self._runner = None
        self._start_time = 0

        # ── Segment review section ──
        self._segment_list = ft.Column(spacing=8)
        self._segment_stats = ft.Text("", size=12, color=TEXT_MUTED)

        # ── Pipeline progress section ──
        self._timer_text = ft.Text("⏱ 00:00", size=14, color=TEXT_SECONDARY)
        self._progress_bar = ft.ProgressBar(value=0, color=ACCENT, bgcolor=BORDER, visible=False)
        self._progress_text = ft.Text("", size=12, color=TEXT_MUTED)
        self._agent_cards = ft.Column(spacing=6)

        # ── Log panel ──
        self._log_list = ft.ListView(spacing=2, height=150, auto_scroll=True)

        # ── Preview panel ──
        self._preview = ft.TextField(
            multiline=True,
            min_lines=10,
            max_lines=20,
            read_only=True,
            value="",
            bgcolor=BG_PRIMARY,
            color=TEXT_PRIMARY,
            border_color=BORDER,
            border_radius=BUTTON_BORDER_RADIUS,
            expand=True,
        )

        # ── State ──
        self._phase = "review"  # review | running | done
        self._timer_thread = None

        self._build_controls()

    def refresh(self):
        """Called when tab becomes active — auto split segments."""
        if not self._state.segments and self._state.source_text:
            self._auto_split()
        self._build_controls()

    def _auto_split(self):
        """Split source text into segments."""
        from services.translator_runner import split_text_into_segments
        text = self._state.source_text
        segments = split_text_into_segments(text)
        self._state.segments = segments
        self._build_segment_list()

    def _build_segment_list(self):
        """Build segment cards for review."""
        self._segment_list.controls.clear()
        for i, seg in enumerate(self._state.segments):
            chars = len(seg)
            preview = seg[:100].replace("\n", " ") + ("..." if len(seg) > 100 else "")

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"Đoạn {i+1}", size=13, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Text(f"[{chars:,} ký tự]", size=12, color=TEXT_MUTED),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.CONTENT_CUT,
                            icon_size=16,
                            icon_color=TEXT_MUTED,
                            tooltip="Tách đoạn tại đây",
                            on_click=lambda e, idx=i: self._split_at(idx),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.MERGE_TYPE,
                            icon_size=16,
                            icon_color=TEXT_MUTED,
                            tooltip="Gộp với đoạn sau",
                            on_click=lambda e, idx=i: self._merge_at(idx),
                        ) if i < len(self._state.segments) - 1 else ft.Container(),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(preview, size=12, color=TEXT_SECONDARY, max_lines=2),
                ], spacing=4),
                **card_style(),
            )
            self._segment_list.controls.append(card)

        total_chars = sum(len(s) for s in self._state.segments)
        self._segment_stats.value = f"Tổng: {len(self._state.segments)} đoạn │ {total_chars:,} ký tự"

    def _split_at(self, index: int):
        """Split a segment in half."""
        seg = self._state.segments[index]
        mid = len(seg) // 2
        # Find nearest paragraph break
        break_pos = seg.rfind("\n\n", 0, mid + 500)
        if break_pos == -1 or break_pos < mid - 500:
            break_pos = seg.rfind("\n", 0, mid + 200)
        if break_pos == -1:
            break_pos = mid

        part1 = seg[:break_pos].strip()
        part2 = seg[break_pos:].strip()
        if part1 and part2:
            self._state.segments[index] = part1
            self._state.segments.insert(index + 1, part2)
            self._build_segment_list()
            self._build_controls()
            self._page.update()

    def _merge_at(self, index: int):
        """Merge segment with next."""
        if index < len(self._state.segments) - 1:
            merged = self._state.segments[index] + "\n\n" + self._state.segments[index + 1]
            self._state.segments[index] = merged
            self._state.segments.pop(index + 1)
            self._build_segment_list()
            self._build_controls()
            self._page.update()

    def _build_controls(self):
        """Build layout based on current phase."""
        if self._phase == "review":
            self.controls = [
                # Segment review
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text("📋 Review điểm cắt", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            self._segment_stats,
                        ]),
                        ft.Divider(height=1, color=BORDER),
                        self._segment_list,
                    ], spacing=8),
                    **card_style(),
                ),
                # Start button
                ft.Row([
                    outlined_button("← Quay lại", icon=ft.Icons.ARROW_BACK,
                                    on_click=lambda e: self._go_back()),
                    ft.Container(expand=True),
                    accent_button("Bắt đầu chuyển đổi ▶", icon=ft.Icons.PLAY_ARROW,
                                  on_click=self._on_start),
                ]),
            ]
        elif self._phase == "running":
            self.controls = [
                # Timer + progress
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            self._timer_text,
                            ft.Container(expand=True),
                            self._progress_text,
                        ]),
                        self._progress_bar,
                    ], spacing=8),
                    **card_style(),
                ),
                # Agent status cards
                ft.Container(
                    content=ft.Column([
                        ft.Text("Pipeline Status", size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        self._agent_cards,
                    ], spacing=8),
                    **card_style(),
                ),
                # Preview
                ft.Container(
                    content=ft.Column([
                        ft.Text("Preview (real-time)", size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        self._preview,
                    ], spacing=8),
                    **card_style(),
                    expand=True,
                ),
                # Log
                ft.Container(
                    content=ft.Column([
                        ft.Text("Log", size=13, color=TEXT_MUTED),
                        self._log_list,
                    ], spacing=4),
                    **card_style(),
                ),
                # Cancel button
                ft.Row([
                    danger_button("Hủy", icon=ft.Icons.CANCEL, on_click=self._on_cancel),
                ]),
            ]
        else:  # done
            self.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=SUCCESS, size=24),
                            ft.Text("Chuyển đổi hoàn tất!", size=16, color=SUCCESS, weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            self._timer_text,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        self._progress_text,
                    ], spacing=8),
                    **card_style(),
                ),
                # Preview
                ft.Container(
                    content=ft.Column([
                        ft.Text("Kết quả preview", size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        self._preview,
                    ], spacing=8),
                    **card_style(),
                    expand=True,
                ),
                # Log
                ft.Container(
                    content=ft.Column([
                        ft.Text("Log", size=13, color=TEXT_MUTED),
                        self._log_list,
                    ], spacing=4),
                    **card_style(),
                ),
                ft.Row([
                    ft.Container(expand=True),
                    accent_button("Hoàn tất → Kết quả", icon=ft.Icons.ARROW_FORWARD,
                                  on_click=lambda e: self._on_complete() if self._on_complete else None),
                ]),
            ]

    def _go_back(self):
        """Go back to config tab."""
        # Access parent TranslatorView
        parent = self.parent
        while parent and not hasattr(parent, '_switch_sub'):
            parent = parent.parent if hasattr(parent, 'parent') else None
        if parent and hasattr(parent, '_switch_sub'):
            parent._switch_sub(1)

    def _on_start(self, e):
        """Start the translation pipeline."""
        self._phase = "running"
        self._start_time = time.time()
        self._preview.value = ""
        self._log_list.controls.clear()
        self._agent_cards.controls.clear()
        self._progress_bar.visible = True
        self._progress_bar.value = 0
        self._state.is_running = True

        self._build_controls()
        self._page.update()

        # Start timer
        self._start_timer()

        # Create DB records
        from db.models import create_translation, create_translation_segments
        tid = create_translation(
            title=self._state.title,
            source_text=self._state.source_text,
            source_lang="vi",
            source_type=self._state.source_type,
            source_url=self._state.source_url,
            config_json=json.dumps(self._state.config, ensure_ascii=False),
        )
        self._state.translation_id = tid

        # Create segments in DB
        create_translation_segments(tid, self._state.segments)

        # Start pipeline
        from services.translator_runner import TranslatorRunner
        self._runner = TranslatorRunner(
            on_progress=self._on_progress,
            on_segment_done=self._on_segment_done,
            on_complete=self._on_pipeline_complete,
            on_error=self._on_pipeline_error,
            on_log=self._on_log,
        )

        fast_mode = self._state.config.get("fast_mode", False)
        # Pass user-confirmed analysis mapping if available (from tab_analysis)
        pre_analysis = self._state.analysis if self._state.analysis else None
        self._runner.start(tid, self._state.config, fast_mode, pre_analysis=pre_analysis)

    def _start_timer(self):
        def _tick():
            while self._state.is_running:
                elapsed = time.time() - self._start_time
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                try:
                    self._timer_text.value = f"⏱ {mins:02d}:{secs:02d}"
                    self._page.update()
                except Exception:
                    break
                time.sleep(1)
        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def _on_progress(self, agent_name, status, segment_index, message):
        """Pipeline progress callback."""
        def _apply():
            try:
                icon_map = {"waiting": "⏳", "running": "⟳", "passed": "✅", "failed": "❌", "retrying": "🔄"}
                icon = icon_map.get(status, "⏳")

                # Update or add agent card
                label = f"{icon} {agent_name}"
                if segment_index >= 0:
                    total = len(self._state.segments)
                    label += f" — Đoạn {segment_index+1}/{total}"
                if message:
                    label += f" │ {message[:60]}"

                # Update progress bar
                if self._state.segments:
                    from db.models import get_translation
                    t = get_translation(self._state.translation_id)
                    if t:
                        completed = t.get("completed_segments", 0)
                        total = t.get("total_segments", 1)
                        self._progress_bar.value = completed / total if total > 0 else 0
                        self._progress_text.value = f"{completed}/{total} đoạn"

                # Simple agent status display
                color_map = {"waiting": TEXT_MUTED, "running": INFO, "passed": SUCCESS, "failed": DANGER, "retrying": WARNING}
                color = color_map.get(status, TEXT_MUTED)

                # Find existing or add new
                found = False
                for ctrl in list(self._agent_cards.controls):
                    if hasattr(ctrl, '_agent_key') and ctrl._agent_key == agent_name:
                        ctrl.content.value = label
                        ctrl.content.color = color
                        found = True
                        break
                if not found:
                    text = ft.Text(label, size=13, color=color)
                    container = ft.Container(content=text, padding=ft.padding.symmetric(horizontal=8, vertical=4))
                    container._agent_key = agent_name
                    self._agent_cards.controls.append(container)

                self._page.update()
            except Exception:
                pass  # Ignore Flet UI diff race conditions

        self._page.run_thread(_apply)

    def _on_segment_done(self, segment_index, result_text):
        """Called when a segment translation is complete."""
        def _apply():
            try:
                current = self._preview.value or ""
                separator = f"\n\n{'─' * 30}\n【Đoạn {segment_index+1}】\n\n" if current else f"【Đoạn {segment_index+1}】\n\n"
                self._preview.value = current + separator + result_text
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_pipeline_complete(self, translation_id):
        """Pipeline finished successfully."""
        def _apply():
            try:
                self._state.is_running = False
                self._phase = "done"

                elapsed = time.time() - self._start_time
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                self._timer_text.value = f"⏱ {mins:02d}:{secs:02d}"
                self._progress_bar.value = 1.0
                self._progress_text.value = f"Hoàn tất trong {mins}m {secs}s"

                from db.models import get_translation
                t = get_translation(translation_id)
                if t and t.get("result_text"):
                    self._state.final_text = t["result_text"]

                self._build_controls()
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_pipeline_error(self, message):
        """Pipeline error."""
        def _apply():
            try:
                self._state.is_running = False
                show_snackbar(self._page, f"Lỗi: {message}", bgcolor="#EF4444", duration=5000)
                self._add_log("ERROR", message)
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_log(self, timestamp, agent, message):
        """Add log entry."""
        def _apply():
            try:
                self._add_log(agent, message, timestamp)
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _add_log(self, agent, message, timestamp=None):
        if not timestamp:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_list.controls.append(
            ft.Text(f"[{timestamp}] {agent}: {message}", size=11, color=TEXT_MUTED,
                    font_family="Consolas")
        )

    def _on_cancel(self, e):
        if self._runner:
            self._runner.cancel()
        self._state.is_running = False
        show_snackbar(self._page, "Đã hủy pipeline")

    def reset(self):
        self._phase = "review"
        self._preview.value = ""
        self._log_list.controls.clear()
        self._agent_cards.controls.clear()
        self._progress_bar.value = 0
        self._progress_bar.visible = False
        self._progress_text.value = ""
        self._timer_text.value = "⏱ 00:00"
        self._segment_list.controls.clear()
        self._build_controls()
