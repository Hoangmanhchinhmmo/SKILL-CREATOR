"""
Tab Result — Editor with 3 modes (Edit/Preview/Split) + history.
"""

import os
import datetime
import threading

import flet as ft
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, SUCCESS, DANGER, INFO,
    card_style, accent_button, outlined_button, danger_button, show_snackbar,
    CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)


class TabResult(ft.Column):
    """Result sub-tab — editor + history."""

    def __init__(self, page: ft.Page, state, on_new=None):
        super().__init__(expand=True, spacing=12)
        self._page = page
        self._state = state
        self._on_new = on_new
        self._mode = "split"  # edit / preview / split
        self._auto_save_timer = None

        # ── Editor fields ──
        self._result_editor = ft.TextField(
            multiline=True,
            min_lines=15,
            max_lines=30,
            value="",
            bgcolor=BG_ELEVATED,
            color=TEXT_PRIMARY,
            border_color=BORDER,
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            border_radius=BUTTON_BORDER_RADIUS,
            expand=True,
            on_change=self._on_edit_change,
        )

        self._source_viewer = ft.TextField(
            multiline=True,
            min_lines=15,
            max_lines=30,
            read_only=True,
            value="",
            bgcolor=BG_PRIMARY,
            color=TEXT_SECONDARY,
            border_color=BORDER,
            border_radius=BUTTON_BORDER_RADIUS,
            expand=True,
        )

        self._preview_md = ft.Markdown(
            value="",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            expand=True,
        )

        # ── Stats ──
        self._stats_text = ft.Text("", size=12, color=TEXT_MUTED)

        # ── History ──
        self._history_list = ft.Column(spacing=6)
        self._history_visible = False

        self._build_controls()

    def refresh(self):
        """Load data from state."""
        if self._state.final_text:
            self._result_editor.value = self._state.final_text
            self._source_viewer.value = self._state.source_text or ""
            self._update_stats()
        self._load_history()
        self._build_controls()

    def _build_controls(self):
        # Mode buttons
        modes = [
            ("edit", "Edit", ft.Icons.EDIT),
            ("preview", "Preview", ft.Icons.VISIBILITY),
            ("split", "Split", ft.Icons.VERTICAL_SPLIT),
        ]
        mode_buttons = []
        for key, label, icon in modes:
            is_active = self._mode == key
            mode_buttons.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, size=16, color=ACCENT if is_active else TEXT_MUTED),
                        ft.Text(label, size=12, color=ACCENT if is_active else TEXT_MUTED),
                    ], spacing=4),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border=ft.border.all(1, ACCENT if is_active else BORDER),
                    border_radius=BUTTON_BORDER_RADIUS,
                    on_click=lambda e, k=key: self._switch_mode(k),
                    ink=True,
                )
            )

        toolbar = ft.Container(
            content=ft.Row([
                ft.Row(mode_buttons, spacing=4),
                ft.Container(expand=True),
                self._stats_text,
                ft.Container(width=16),
                ft.IconButton(icon=ft.Icons.CONTENT_COPY, icon_size=18, icon_color=TEXT_MUTED,
                              tooltip="Copy", on_click=self._on_copy),
                ft.IconButton(icon=ft.Icons.SAVE_ALT, icon_size=18, icon_color=TEXT_MUTED,
                              tooltip="Export .md", on_click=self._on_export),
                ft.IconButton(icon=ft.Icons.SAVE, icon_size=18, icon_color=ACCENT,
                              tooltip="Lưu (Ctrl+S)", on_click=self._on_save),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            **card_style(),
        )

        # Editor area
        if self._mode == "edit":
            editor_area = ft.Container(
                content=self._result_editor,
                expand=True,
            )
        elif self._mode == "preview":
            editor_area = ft.Container(
                content=ft.Column([self._preview_md], scroll=ft.ScrollMode.AUTO, expand=True),
                expand=True,
                **card_style(),
            )
        else:  # split
            editor_area = ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Truyện gốc", size=12, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                        self._source_viewer,
                    ], spacing=4, expand=True),
                    expand=True,
                ),
                ft.VerticalDivider(width=1, color=BORDER),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Kết quả (Nhật)", size=12, color=TEXT_MUTED, weight=ft.FontWeight.BOLD),
                        self._result_editor,
                    ], spacing=4, expand=True),
                    expand=True,
                ),
            ], spacing=8, expand=True)

        # History section
        history_toggle = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.HISTORY, size=16, color=TEXT_MUTED),
                ft.Text("Lịch sử dịch", size=13, color=TEXT_MUTED),
                ft.Icon(ft.Icons.EXPAND_MORE if not self._history_visible else ft.Icons.EXPAND_LESS,
                        size=16, color=TEXT_MUTED),
            ], spacing=6),
            on_click=self._toggle_history,
            ink=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        history_section = ft.Container(
            content=ft.Column([
                history_toggle,
                ft.Container(
                    content=self._history_list,
                    visible=self._history_visible,
                    padding=ft.padding.only(top=8),
                ),
            ], spacing=0),
            **card_style(),
        )

        # Action buttons
        actions = ft.Row([
            accent_button("Dịch truyện mới", icon=ft.Icons.ADD, on_click=self._on_new_click),
        ])

        self.controls = [toolbar, editor_area, history_section, actions]

    def _switch_mode(self, mode: str):
        self._mode = mode
        if mode == "preview":
            self._preview_md.value = self._result_editor.value or ""
        self._build_controls()
        self._page.update()

    def _on_edit_change(self, e):
        self._update_stats()
        # Auto-save after 30s
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
        self._auto_save_timer = threading.Timer(30.0, self._auto_save)
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def _update_stats(self):
        text = self._result_editor.value or ""
        chars = len(text)
        lines = text.count("\n") + 1 if text else 0
        tts_min = chars / 700  # ~700 chars/min for Japanese TTS
        self._stats_text.value = f"📊 {chars:,}字 │ {lines}行 │ ⏱ TTS: ~{tts_min:.0f}分"

    def _on_copy(self, e):
        text = self._result_editor.value or ""
        if text:
            self._page.run_task(ft.Clipboard().set, text)
            show_snackbar(self._page, "Đã copy!")

    def _on_export(self, e):
        text = self._result_editor.value or ""
        if not text:
            show_snackbar(self._page, "Không có nội dung để export", bgcolor="#EF4444")
            return

        title = self._state.title or "translation"
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()[:50]
        filename = f"{safe_title}.md"

        # Save to Downloads or Desktop
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(downloads):
            downloads = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(downloads, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {self._state.title}\n\n")
            f.write(text)

        show_snackbar(self._page, f"Đã export: {filepath}")

    def _on_save(self, e=None):
        self._save_to_db()
        show_snackbar(self._page, "Đã lưu!")

    def _auto_save(self):
        try:
            self._save_to_db()
        except Exception:
            pass

    def _save_to_db(self):
        if self._state.translation_id:
            from db.models import update_translation
            update_translation(
                self._state.translation_id,
                result_text=self._result_editor.value or "",
            )

    def _toggle_history(self, e):
        self._history_visible = not self._history_visible
        self._build_controls()
        self._page.update()

    def _load_history(self):
        """Load translation history."""
        self._history_list.controls.clear()
        try:
            from db.models import list_translations
            items, total = list_translations(per_page=10)
            for item in items:
                status = item.get("status", "draft")
                color_map = {"done": SUCCESS, "failed": DANGER, "translating": INFO, "draft": TEXT_MUTED}
                status_color = color_map.get(status, TEXT_MUTED)

                created = item.get("created_at", "")
                if created:
                    try:
                        dt = datetime.datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        pass

                card = ft.Container(
                    content=ft.Row([
                        ft.Text(f"#{item['id']}", size=12, color=TEXT_MUTED, width=30),
                        ft.Text(item.get("title", "Untitled")[:30], size=13, color=TEXT_PRIMARY, expand=True),
                        ft.Container(
                            content=ft.Text(status.upper(), size=10, color="#FFF", weight=ft.FontWeight.BOLD),
                            bgcolor=status_color,
                            border_radius=4,
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                        ),
                        ft.Text(created, size=11, color=TEXT_MUTED),
                        ft.IconButton(
                            icon=ft.Icons.OPEN_IN_NEW, icon_size=16, icon_color=TEXT_MUTED,
                            tooltip="Mở",
                            on_click=lambda e, tid=item["id"]: self._load_translation(tid),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=DANGER,
                            tooltip="Xóa",
                            on_click=lambda e, tid=item["id"]: self._delete_translation(tid),
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    bgcolor=BG_ELEVATED,
                    border_radius=BUTTON_BORDER_RADIUS,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border=ft.border.all(1, BORDER),
                )
                self._history_list.controls.append(card)

            if not items:
                self._history_list.controls.append(
                    ft.Text("Chưa có lịch sử dịch", size=12, color=TEXT_MUTED, italic=True)
                )
        except Exception:
            pass

    def _load_translation(self, translation_id: int):
        """Load a previous translation into editor."""
        from db.models import get_translation
        t = get_translation(translation_id)
        if t:
            self._state.translation_id = translation_id
            self._state.title = t.get("title", "")
            self._state.source_text = t.get("source_text", "")
            self._state.final_text = t.get("result_text", "")
            self._result_editor.value = t.get("result_text", "")
            self._source_viewer.value = t.get("source_text", "")
            self._update_stats()
            self._build_controls()
            self._page.update()
            show_snackbar(self._page, f"Đã load #{translation_id}")

    def _delete_translation(self, translation_id: int):
        """Delete a translation."""
        from db.models import delete_translation
        delete_translation(translation_id)
        self._load_history()
        self._build_controls()
        self._page.update()
        show_snackbar(self._page, f"Đã xóa #{translation_id}")

    def _on_new_click(self, e):
        if self._on_new:
            self._on_new()

    def reset(self):
        self._result_editor.value = ""
        self._source_viewer.value = ""
        self._preview_md.value = ""
        self._stats_text.value = ""
        self._mode = "split"
        self._history_visible = False
        self._build_controls()
