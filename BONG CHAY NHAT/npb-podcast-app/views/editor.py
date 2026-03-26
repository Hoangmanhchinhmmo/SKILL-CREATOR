"""
Editor Tab — Edit/Preview/Split modes, auto-save, export.
"""

import threading
import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, FONT_MONO,
    card_style, accent_button, outlined_button,
)
from db.models import get_article, update_article_content

TTS_CHARS_PER_MIN = 700
AUTOSAVE_INTERVAL = 30  # seconds


class EditorTab(ft.Column):
    """Article editor with Edit/Preview/Split modes."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=12)
        self._page = page
        self.article_id: int | None = None
        self.original_content: str = ""
        self.current_mode = "edit"  # edit, preview, split
        self._autosave_timer: threading.Timer | None = None
        self._dirty = False

        self._build_empty()

    def _build_empty(self):
        """Show empty state when no article is loaded."""
        self.controls = [
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=48, color=TEXT_MUTED),
                    ft.Text("Chọn một bài viết để chỉnh sửa", size=14, color=TEXT_MUTED),
                    ft.Text("Từ Dashboard, Pipeline hoặc History", size=12, color=TEXT_MUTED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                alignment=ft.Alignment(0, 0),
                expand=True,
            )
        ]

    def load_article(self, article_id: int):
        """Load an article into the editor."""
        article = get_article(article_id)
        if not article:
            return

        self.article_id = article_id
        self.original_content = article["content"]
        self._dirty = False
        self._build_editor(article)
        self._page.update()

    def _build_editor(self, article: dict):
        """Build the full editor UI."""
        # Header
        topic = article["topic"][:60]
        format_type = article["format"]
        created = (article.get("created_at") or "")[:16]
        updated = (article.get("updated_at") or "")[:16]

        # Mode toggle
        self.mode_group = ft.RadioGroup(
            value=self.current_mode,
            on_change=self._on_mode_change,
            content=ft.Row([
                ft.Radio(value="edit", label="Edit", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY, size=12)),
                ft.Radio(value="preview", label="Preview", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY, size=12)),
                ft.Radio(value="split", label="Split", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY, size=12)),
            ], spacing=4),
        )

        # Editor textarea
        self.editor_field = ft.TextField(
            value=article["content"],
            multiline=True,
            min_lines=20,
            max_lines=50,
            expand=True,
            bgcolor=BG_ELEVATED,
            color=TEXT_PRIMARY,
            border_color=BORDER,
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            text_style=ft.TextStyle(font_family=FONT_MONO, size=13),
            on_change=self._on_content_change,
        )

        # Preview
        self.preview_md = ft.Markdown(
            value=article["content"],
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            expand=True,
        )

        # Stats bar
        content = article["content"]
        chars = len(content)
        lines = content.count("\n") + 1
        tts_min = chars / TTS_CHARS_PER_MIN

        self.stats_text = ft.Text(
            f"Chars: {chars:,}  │  Lines: {lines}  │  TTS: ~{tts_min:.0f}分",
            size=12, color=TEXT_MUTED,
        )

        # Save message
        self.save_msg = ft.Text("", size=12, color=SUCCESS)

        # Content area (changes by mode)
        self.content_area = ft.Container(expand=True)
        self._update_content_mode()

        self.controls = [
            # Header
            ft.Row([
                ft.Text(f"Editor — {topic}", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY, expand=True),
            ]),
            ft.Row([
                ft.Text(format_type, size=12, color=TEXT_SECONDARY),
                ft.Text(f"Tạo: {created}", size=12, color=TEXT_MUTED),
                ft.Text(f"Sửa: {updated}" if updated else "", size=12, color=TEXT_MUTED),
                ft.Container(expand=True),
                self.mode_group,
            ], spacing=12),

            # Content
            self.content_area,

            # Stats bar
            ft.Container(
                content=self.stats_text,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                bgcolor=BG_CARD,
                border=ft.border.all(1, BORDER),
                border_radius=4,
            ),

            # Action buttons
            ft.Row([
                accent_button("Lưu", icon=ft.Icons.SAVE_ROUNDED, on_click=self._on_save),
                outlined_button("Copy", icon=ft.Icons.COPY_ROUNDED, on_click=self._on_copy),
                outlined_button("Export .md", icon=ft.Icons.FILE_DOWNLOAD_ROUNDED, on_click=self._on_export),
                ft.Container(expand=True),
                outlined_button("Undo về bản gốc", icon=ft.Icons.UNDO_ROUNDED, on_click=self._on_undo),
                self.save_msg,
            ], spacing=8),
        ]

        # Start autosave
        self._start_autosave()

    def _update_content_mode(self):
        """Update the content area based on current mode."""
        if self.current_mode == "edit":
            self.content_area.content = self.editor_field
        elif self.current_mode == "preview":
            self.content_area.content = ft.Container(
                content=self.preview_md,
                bgcolor=BG_CARD,
                border=ft.border.all(1, BORDER),
                border_radius=6,
                padding=16,
                expand=True,
            )
        elif self.current_mode == "split":
            self.content_area.content = ft.Row([
                ft.Container(content=self.editor_field, expand=True),
                ft.VerticalDivider(width=1, color=BORDER),
                ft.Container(
                    content=self.preview_md,
                    bgcolor=BG_CARD,
                    border=ft.border.all(1, BORDER),
                    border_radius=6,
                    padding=16,
                    expand=True,
                ),
            ], expand=True, spacing=8)

    def _on_mode_change(self, e):
        self.current_mode = e.control.value
        self._update_content_mode()
        self._page.update()

    def _on_content_change(self, e):
        """Content changed — update preview and stats."""
        self._dirty = True
        content = self.editor_field.value
        self.preview_md.value = content

        chars = len(content)
        lines = content.count("\n") + 1
        tts_min = chars / TTS_CHARS_PER_MIN
        self.stats_text.value = f"Chars: {chars:,}  │  Lines: {lines}  │  TTS: ~{tts_min:.0f}分"

        self._page.update()

    def _on_save(self, e=None):
        """Save content to SQLite."""
        if not self.article_id:
            return
        content = self.editor_field.value
        update_article_content(self.article_id, content)
        self._dirty = False
        self.save_msg.value = "Đã lưu!"
        self.save_msg.color = SUCCESS
        self._page.update()

    def _on_copy(self, e):
        content = self.editor_field.value
        self._page.run_task(ft.Clipboard().set, content)
        show_snackbar(self._page, "Đã copy nội dung", 2000)

    def _on_export(self, e):
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                with open(result.path, "w", encoding="utf-8") as f:
                    f.write(self.editor_field.value)
                show_snackbar(self._page, f"Đã export: {result.path}", 3000)

        picker = ft.FilePicker(on_result=on_result)
        self._page.overlay.append(picker)
        self._page.update()
        picker.save_file(
            file_name="podcast_script.md",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["md", "txt"],
        )

    def _on_undo(self, e):
        """Revert to original content."""
        def on_confirm(e):
            close_dialog(self._page, dialog)
            self.editor_field.value = self.original_content
            self.preview_md.value = self.original_content
            self._on_content_change(None)
            self._on_save()

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Undo về bản gốc?"),
            content=ft.Text("Tất cả thay đổi sẽ bị mất, quay về nội dung gốc khi tạo."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Undo"), style=ft.ButtonStyle(color=ACCENT), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _start_autosave(self):
        """Start autosave timer."""
        self._stop_autosave()

        def autosave():
            if self._dirty and self.article_id:
                try:
                    content = self.editor_field.value
                    update_article_content(self.article_id, content)
                    self._dirty = False
                except Exception:
                    pass
            self._autosave_timer = threading.Timer(AUTOSAVE_INTERVAL, autosave)
            self._autosave_timer.daemon = True
            self._autosave_timer.start()

        self._autosave_timer = threading.Timer(AUTOSAVE_INTERVAL, autosave)
        self._autosave_timer.daemon = True
        self._autosave_timer.start()

    def _stop_autosave(self):
        if self._autosave_timer:
            self._autosave_timer.cancel()
            self._autosave_timer = None
