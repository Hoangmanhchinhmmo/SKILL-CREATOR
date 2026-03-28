"""
Tab Analysis — Run Analyzer + display editable mapping for user review.
User can edit names, places, culture, organizations before translation starts.
"""

import json
import threading

import flet as ft
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT,
    SUCCESS, DANGER, INFO, WARNING,
    card_style, accent_button, outlined_button, danger_button, show_snackbar,
    CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)


class TabAnalysis(ft.Column):
    """Analysis sub-tab — run Analyzer, show editable mapping, user confirms."""

    def __init__(self, page: ft.Page, state, on_next=None, on_back=None):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self._state = state
        self._on_next = on_next
        self._on_back = on_back

        # Analysis state
        self._phase = "idle"  # idle | analyzing | done | error
        self._error_msg = ""

        # Editable mapping data (lists of [original, japanese] pairs)
        self._names_rows: list[list[str]] = []
        self._places_rows: list[list[str]] = []
        self._culture_rows: list[list[str]] = []
        self._orgs_rows: list[list[str]] = []
        self._characters_info: list[dict] = []
        self._analysis_meta: dict = {}  # source_lang, tone, notes, etc.

        # UI containers
        self._status_text = ft.Text("", size=13, color=TEXT_MUTED)
        self._names_table = ft.Column(spacing=4)
        self._places_table = ft.Column(spacing=4)
        self._culture_table = ft.Column(spacing=4)
        self._orgs_table = ft.Column(spacing=4)
        self._characters_panel = ft.Column(spacing=4)
        self._notes_field = ft.TextField(
            multiline=True, min_lines=2, max_lines=4,
            value="", bgcolor=BG_PRIMARY, color=TEXT_PRIMARY,
            border_color=BORDER, border_radius=BUTTON_BORDER_RADIUS,
            label="Ghi chú them (notes)",
        )

        self._build_controls()

    def refresh(self):
        """Called when tab becomes active. Auto-run analysis if not done."""
        if self._phase == "idle" and self._state.source_text:
            self._start_analysis()
        elif self._phase == "done":
            self._build_controls()

    def _start_analysis(self):
        """Run Analyzer in background thread."""
        self._phase = "analyzing"
        self._status_text.value = "Đang phân tích kịch bản... (có thể mất 30-60s)"
        self._status_text.color = INFO
        self._build_controls()
        self._page.update()

        def _run():
            try:
                import sys
                import importlib
                from services.pipeline_runner import _inject_settings_to_env
                import os

                _inject_settings_to_env()

                # Set analyzer model
                model_analyzer = self._state.config.get("model_analyzer", "gemini-2.5-flash")
                os.environ["GEMINI_MODEL_DATA"] = model_analyzer

                if "config" in sys.modules:
                    importlib.reload(sys.modules["config"])
                if "agents" in sys.modules:
                    importlib.reload(sys.modules["agents"])
                from agents import _call_gemini
                from services.translator_runner import TranslatorRunner

                runner = TranslatorRunner()
                analysis = runner._run_analyzer(
                    self._state.source_text,
                    self._state.config,
                    _call_gemini,
                )

                def _apply():
                    self._state.analysis = analysis
                    self._load_mapping_from_analysis(analysis)
                    self._phase = "done"
                    self._status_text.value = f"Phân tích hoàn tất — Ngôn ngữ: {analysis.get('source_lang', '?')} | Tone: {analysis.get('tone', '?')}"
                    self._status_text.color = SUCCESS
                    self._build_controls()
                    self._page.update()

                self._page.run_thread(_apply)

            except Exception as e:
                def _err():
                    self._phase = "error"
                    self._error_msg = str(e)
                    self._status_text.value = f"Lỗi phân tích: {e}"
                    self._status_text.color = DANGER
                    self._build_controls()
                    self._page.update()
                self._page.run_thread(_err)

        threading.Thread(target=_run, daemon=True).start()

    def _load_mapping_from_analysis(self, analysis: dict):
        """Load analysis result into editable rows.
        Supports both formats:
        - New: {"name": {"ja": "...", "vi": "..."}}
        - Old: {"name": "japanese_value"}
        Rows are [original, japanese, vietnamese_meaning].
        """
        mapping = analysis.get("mapping", {})

        def _parse_section(section: dict) -> list[list[str]]:
            rows = []
            for k, v in section.items():
                if isinstance(v, dict):
                    rows.append([k, v.get("ja", ""), v.get("vi", "")])
                else:
                    rows.append([k, str(v), ""])
            return rows

        self._names_rows = _parse_section(mapping.get("names", {}))
        self._places_rows = _parse_section(mapping.get("places", {}))
        self._culture_rows = _parse_section(mapping.get("culture", {}))
        self._orgs_rows = _parse_section(mapping.get("organizations", {}))

        # Characters summary
        self._characters_info = analysis.get("characters_summary", [])

        # Meta
        self._analysis_meta = {
            "source_lang": analysis.get("source_lang", ""),
            "has_foreign_elements": analysis.get("has_foreign_elements", False),
            "is_foreign_setting": analysis.get("is_foreign_setting", False),
            "original_setting_country": analysis.get("original_setting_country", ""),
            "tone": analysis.get("tone", ""),
        }
        self._notes_field.value = analysis.get("notes", "")

    def _build_mapping_table(self, rows: list[list[str]], category: str) -> ft.Column:
        """Build an editable 3-column table: Tên gốc | Tên Nhật | Nghĩa TV."""
        controls = []

        # Header
        controls.append(ft.Row([
            ft.Container(
                ft.Text("Tên gốc", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                expand=2,
            ),
            ft.Container(
                ft.Text("Tên Nhật", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                expand=2,
            ),
            ft.Container(
                ft.Text("Nghĩa tiếng Việt", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                expand=3,
            ),
            ft.Container(width=36),  # delete button space
        ], spacing=8))

        # Rows
        for i, row in enumerate(rows):
            orig_field = ft.TextField(
                value=row[0], bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
                border_color=BORDER, border_radius=4,
                content_padding=ft.padding.symmetric(horizontal=8, vertical=6),
                text_size=13, expand=2,
                on_change=lambda e, idx=i, cat=category: self._on_mapping_edit(cat, idx, 0, e.control.value),
            )
            jp_field = ft.TextField(
                value=row[1], bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
                border_color=BORDER, border_radius=4,
                content_padding=ft.padding.symmetric(horizontal=8, vertical=6),
                text_size=13, expand=2,
                on_change=lambda e, idx=i, cat=category: self._on_mapping_edit(cat, idx, 1, e.control.value),
            )
            vi_field = ft.TextField(
                value=row[2] if len(row) > 2 else "", bgcolor=BG_ELEVATED, color=TEXT_SECONDARY,
                border_color=BORDER, border_radius=4,
                content_padding=ft.padding.symmetric(horizontal=8, vertical=6),
                text_size=12, expand=3,
                text_style=ft.TextStyle(italic=True),
                on_change=lambda e, idx=i, cat=category: self._on_mapping_edit(cat, idx, 2, e.control.value),
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=DANGER,
                tooltip="Xóa",
                on_click=lambda e, idx=i, cat=category: self._delete_row(cat, idx),
            )
            controls.append(ft.Row([orig_field, jp_field, vi_field, delete_btn], spacing=8))

        # Add button
        controls.append(
            ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, size=14, color=ACCENT),
                    ft.Text("Thêm mới", size=12, color=ACCENT),
                ], spacing=4),
                on_click=lambda e, cat=category: self._add_row(cat),
            )
        )

        return ft.Column(controls, spacing=4)

    def _get_rows(self, category: str) -> list[list[str]]:
        return {"names": self._names_rows, "places": self._places_rows,
                "culture": self._culture_rows, "orgs": self._orgs_rows}[category]

    def _on_mapping_edit(self, category: str, row_idx: int, col_idx: int, value: str):
        """Handle inline edit of a mapping cell."""
        rows = self._get_rows(category)
        if row_idx < len(rows):
            rows[row_idx][col_idx] = value

    def _delete_row(self, category: str, row_idx: int):
        rows = self._get_rows(category)
        if row_idx < len(rows):
            rows.pop(row_idx)
            self._build_controls()
            self._page.update()

    def _add_row(self, category: str):
        rows = self._get_rows(category)
        rows.append(["", "", ""])
        self._build_controls()
        self._page.update()

    def _build_characters_panel(self) -> ft.Column:
        """Build read-only characters summary with Vietnamese role."""
        controls = []
        for ch in self._characters_info:
            name = ch.get("original_name", "?")
            jp = ch.get("japanese_name", "?")
            role = ch.get("role", "")
            role_vi = ch.get("role_vi", "")
            first = ch.get("first_appearance", "")

            # Role display: prefer Vietnamese, fallback to Japanese
            role_display = role_vi if role_vi else role

            controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Text(f"{name}", size=13, color=TEXT_SECONDARY, expand=True),
                            ft.Text(f"→ {jp}", size=13, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text(role_display, size=12, color=INFO),
                        ], spacing=8),
                    ], spacing=2),
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                    bgcolor=BG_ELEVATED,
                    border_radius=4,
                )
            )
            if first:
                controls.append(
                    ft.Text(f"   Xuất hiện: {first[:80]}", size=11, color=TEXT_MUTED,
                            italic=True),
                )
        if not controls:
            controls.append(ft.Text("Không có thông tin nhân vật", size=12, color=TEXT_MUTED))
        return ft.Column(controls, spacing=4)

    def _collect_mapping(self) -> dict:
        """Collect mapping for translator — only {original: japanese}.
        Vietnamese meaning is for user review only, not sent to translator.
        """
        return {
            "names": {r[0]: r[1] for r in self._names_rows if r[0].strip()},
            "places": {r[0]: r[1] for r in self._places_rows if r[0].strip()},
            "culture": {r[0]: r[1] for r in self._culture_rows if r[0].strip()},
            "organizations": {r[0]: r[1] for r in self._orgs_rows if r[0].strip()},
        }

    def _build_controls(self):
        """Build layout based on phase."""
        if self._phase == "idle":
            self.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text("Phân tích kịch bản", size=16, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Text("Nhấn 'Bắt đầu phân tích' để AI phân tích toàn bộ truyện và tạo mapping tên, địa điểm.",
                                size=13, color=TEXT_SECONDARY),
                        ft.Container(height=8),
                        accent_button("Bắt đầu phân tích", icon=ft.Icons.AUTO_FIX_HIGH,
                                      on_click=lambda e: self._start_analysis()),
                    ], spacing=8),
                    **card_style(),
                ),
                ft.Row([
                    outlined_button("← Quay lại", icon=ft.Icons.ARROW_BACK,
                                    on_click=lambda e: self._on_back() if self._on_back else None),
                ]),
            ]

        elif self._phase == "analyzing":
            self.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text("Đang phân tích kịch bản...", size=16, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.ProgressBar(color=ACCENT, bgcolor=BORDER),
                        self._status_text,
                    ], spacing=12),
                    **card_style(),
                ),
            ]

        elif self._phase == "error":
            self.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text("Lỗi phân tích", size=16, color=DANGER, weight=ft.FontWeight.BOLD),
                        ft.Text(self._error_msg, size=13, color=TEXT_SECONDARY),
                        ft.Container(height=8),
                        accent_button("Thử lại", icon=ft.Icons.REFRESH,
                                      on_click=lambda e: self._retry()),
                    ], spacing=8),
                    **card_style(),
                ),
                ft.Row([
                    outlined_button("← Quay lại", icon=ft.Icons.ARROW_BACK,
                                    on_click=lambda e: self._on_back() if self._on_back else None),
                ]),
            ]

        elif self._phase == "done":
            # Meta info
            meta_text = (
                f"Ngôn ngữ goc: {self._analysis_meta.get('source_lang', '?')} | "
                f"Bối cảnh gốc: {self._analysis_meta.get('original_setting_country', '?')} | "
                f"Tone: {self._analysis_meta.get('tone', '?')}"
            )
            meta_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ANALYTICS, size=18, color=SUCCESS),
                        ft.Text("Kết quả phân tích", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        self._status_text,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(meta_text, size=12, color=TEXT_SECONDARY),
                ], spacing=6),
                **card_style(),
            )

            # Characters summary
            chars_card = ft.Container(
                content=ft.Column([
                    ft.Text("Nhân vật", size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=BORDER),
                    self._build_characters_panel(),
                ], spacing=8),
                **card_style(),
            )

            # Editable mapping sections
            names_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"Tên người ({len(self._names_rows)})", size=14,
                                color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        ft.Text("Chỉnh sửa tên trước khi dịch", size=11, color=TEXT_MUTED, italic=True),
                    ]),
                    ft.Divider(height=1, color=BORDER),
                    self._build_mapping_table(self._names_rows, "names"),
                ], spacing=8),
                **card_style(),
            )

            places_card = ft.Container(
                content=ft.Column([
                    ft.Text(f"Địa điểm ({len(self._places_rows)})", size=14,
                            color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=BORDER),
                    self._build_mapping_table(self._places_rows, "places"),
                ], spacing=8),
                **card_style(),
            )

            culture_card = ft.Container(
                content=ft.Column([
                    ft.Text(f"Văn hóa ({len(self._culture_rows)})", size=14,
                            color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=BORDER),
                    self._build_mapping_table(self._culture_rows, "culture"),
                ], spacing=8),
                **card_style(),
            )

            orgs_card = ft.Container(
                content=ft.Column([
                    ft.Text(f"Tổ chức ({len(self._orgs_rows)})", size=14,
                            color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1, color=BORDER),
                    self._build_mapping_table(self._orgs_rows, "orgs"),
                ], spacing=8),
                **card_style(),
            )

            notes_card = ft.Container(
                content=ft.Column([
                    ft.Text("Ghi chú", size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    self._notes_field,
                ], spacing=8),
                **card_style(),
            )

            # Buttons
            buttons = ft.Row([
                outlined_button("← Quay lại", icon=ft.Icons.ARROW_BACK,
                                on_click=lambda e: self._on_back() if self._on_back else None),
                outlined_button("Phân tích lại", icon=ft.Icons.REFRESH,
                                on_click=lambda e: self._retry()),
                ft.Container(expand=True),
                accent_button("Xác nhận mapping → Bắt đầu dịch", icon=ft.Icons.CHECK_CIRCLE,
                              on_click=self._on_confirm),
            ])

            self.controls = [
                meta_card, chars_card, names_card, places_card,
                culture_card, orgs_card, notes_card, buttons,
            ]

    def _retry(self):
        """Re-run analysis."""
        self._phase = "idle"
        self._start_analysis()

    def _on_confirm(self, e):
        """User confirms mapping — save to state and proceed."""
        # Collect edited mapping
        final_mapping = self._collect_mapping()

        # Build final analysis dict
        final_analysis = {
            **self._analysis_meta,
            "mapping": final_mapping,
            "characters_summary": self._characters_info,
            "notes": self._notes_field.value or "",
        }

        # Save to state
        self._state.analysis = final_analysis

        show_snackbar(self._page, f"Đã xác nhận mapping: {len(final_mapping.get('names', {}))} ten, "
                      f"{len(final_mapping.get('places', {}))} dia diem")

        if self._on_next:
            self._on_next()

    def reset(self):
        """Reset for new translation."""
        self._phase = "idle"
        self._error_msg = ""
        self._names_rows = []
        self._places_rows = []
        self._culture_rows = []
        self._orgs_rows = []
        self._characters_info = []
        self._analysis_meta = {}
        self._notes_field.value = ""
        self._status_text.value = ""
        self._build_controls()
