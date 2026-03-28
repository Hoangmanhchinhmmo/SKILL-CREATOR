"""
Tab Input — 4 input sources: Paste text, Import file, YouTube URL, Web URL.
"""

import flet as ft
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER, BORDER_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    SUCCESS, DANGER, INFO, WARNING,
    card_style, accent_button, input_field, show_snackbar,
    CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)


SOURCE_MODES = [
    ("📝", "Paste"),
    ("▶", "YouTube"),
    ("🌐", "Web"),
]


class TabInput(ft.Column):
    """Input sub-tab — select source and provide content."""

    def __init__(self, page: ft.Page, state, on_next=None):
        super().__init__(expand=True, spacing=16)
        self._page = page
        self._state = state
        self._on_next = on_next
        self._mode = 0  # 0=paste, 1=file, 2=youtube, 3=web
        self._preview_text = ""

        # Title field
        self._title_field = input_field(label="Tiêu đề truyện", hint="Nhập tiêu đề (tùy chọn)")

        # Mode selector buttons
        self._mode_buttons = self._build_mode_buttons()

        # Paste mode
        self._paste_field = ft.TextField(
            multiline=True,
            min_lines=12,
            max_lines=20,
            hint_text="Dán nội dung truyện ở đây...",
            bgcolor=BG_ELEVATED,
            color=TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=TEXT_MUTED),
            border_color=BORDER,
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            border_radius=BUTTON_BORDER_RADIUS,
            expand=True,
            on_change=self._on_paste_change,
        )

        # (File mode removed)

        # YouTube mode
        self._yt_url_field = input_field(label="YouTube URL", hint="https://youtube.com/watch?v=...", expand=True)
        self._yt_status = ft.Text("", size=12, color=TEXT_MUTED)

        # Web mode
        self._web_url_field = input_field(label="Web URL", hint="https://example.com/truyen/...", expand=True)
        self._web_status = ft.Text("", size=12, color=TEXT_MUTED)

        # Preview
        self._preview = ft.TextField(
            multiline=True,
            min_lines=8,
            max_lines=15,
            read_only=True,
            value="",
            bgcolor=BG_PRIMARY,
            color=TEXT_SECONDARY,
            border_color=BORDER,
            border_radius=BUTTON_BORDER_RADIUS,
            visible=False,
            expand=True,
        )

        # Stats
        self._stats_text = ft.Text("", size=12, color=TEXT_MUTED)

        # Loading
        self._loading = ft.ProgressRing(width=20, height=20, stroke_width=2, color=ACCENT, visible=False)

        # Build layout
        self._input_area = self._build_input_area()
        self._build_controls()

    def _build_mode_buttons(self) -> ft.Row:
        buttons = []
        for i, (icon, label) in enumerate(SOURCE_MODES):
            is_active = i == self._mode
            buttons.append(
                ft.Container(
                    content=ft.Row(
                        [ft.Text(icon, size=16), ft.Text(label, size=13, color=TEXT_PRIMARY if is_active else TEXT_MUTED)],
                        spacing=6,
                    ),
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    bgcolor=BG_ELEVATED if is_active else "transparent",
                    border=ft.border.all(1, ACCENT if is_active else BORDER),
                    border_radius=BUTTON_BORDER_RADIUS,
                    on_click=lambda e, idx=i: self._switch_mode(idx),
                    ink=True,
                )
            )
        return ft.Row(buttons, spacing=8)

    def _build_input_area(self) -> ft.Container:
        """Build input area based on current mode."""
        if self._mode == 0:
            content = ft.Column([self._paste_field], expand=True)
        elif self._mode == 1:
            content = ft.Column([
                ft.Row([
                    self._yt_url_field,
                    ft.ElevatedButton(
                        "Tải subtitle",
                        icon=ft.Icons.DOWNLOAD,
                        bgcolor=ACCENT,
                        color="#FFFFFF",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=BUTTON_BORDER_RADIUS)),
                        on_click=self._on_yt_download,
                    ),
                    self._loading,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._yt_status,
            ])
        else:
            content = ft.Column([
                ft.Row([
                    self._web_url_field,
                    ft.ElevatedButton(
                        "Crawl nội dung",
                        icon=ft.Icons.LANGUAGE,
                        bgcolor=ACCENT,
                        color="#FFFFFF",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=BUTTON_BORDER_RADIUS)),
                        on_click=self._on_web_crawl,
                    ),
                    self._loading,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._web_status,
            ])

        return ft.Container(content=content, **card_style(), expand=True)

    def _build_controls(self):
        """Build the full tab layout."""
        self.controls = [
            # Mode selector
            self._mode_buttons,

            # Title
            self._title_field,

            # Input area
            self._input_area,

            # Preview (visible after input)
            ft.Container(
                content=ft.Column([
                    ft.Text("Preview nội dung", size=13, color=TEXT_SECONDARY, weight=ft.FontWeight.BOLD),
                    self._preview,
                ], spacing=4),
                visible=self._preview.visible,
            ),

            # Stats + Next button
            ft.Row([
                self._stats_text,
                ft.Container(expand=True),
                accent_button("Tiếp tục → Cấu hình", icon=ft.Icons.ARROW_FORWARD, on_click=self._on_next_click),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]

    def _switch_mode(self, mode: int):
        self._mode = mode
        self._mode_buttons = self._build_mode_buttons()
        self._input_area = self._build_input_area()
        self._build_controls()
        self._page.update()

    def _on_paste_change(self, e):
        text = self._paste_field.value or ""
        chars = len(text)
        lines = text.count("\n") + 1 if text else 0
        self._stats_text.value = f"Ký tự: {chars:,} │ Dòng: {lines:,}"
        self._page.update()

    def _on_yt_download(self, e):
        url = self._yt_url_field.value or ""
        if not url.strip():
            show_snackbar(self._page, "Nhập YouTube URL", bgcolor="#EF4444")
            return

        self._loading.visible = True
        self._yt_status.value = "Đang tải subtitle..."
        self._yt_status.color = INFO
        self._page.update()

        import threading
        def _download():
            try:
                from services.input_handler import handle_youtube
                result = handle_youtube(url.strip())
                self._set_result(result.title, result.text, "youtube", url.strip(), result.metadata)
                self._page.run_thread(lambda: self._update_yt_status(f"✅ Đã tải — {result.metadata.get('subtitle_lang', '')}", SUCCESS))
            except Exception as ex:
                self._page.run_thread(lambda: self._update_yt_status(f"❌ {ex}", DANGER))
            finally:
                self._page.run_thread(self._hide_loading)
        threading.Thread(target=_download, daemon=True).start()

    def _on_web_crawl(self, e):
        url = self._web_url_field.value or ""
        if not url.strip():
            show_snackbar(self._page, "Nhập Web URL", bgcolor="#EF4444")
            return

        self._loading.visible = True
        self._web_status.value = "Đang crawl..."
        self._web_status.color = INFO
        self._page.update()

        import threading
        def _crawl():
            try:
                from services.input_handler import handle_web
                result = handle_web(url.strip())
                self._set_result(result.title, result.text, "web", url.strip())
                self._page.run_thread(lambda: self._update_web_status(f"✅ Đã crawl — {len(result.text):,} ký tự", SUCCESS))
            except Exception as ex:
                self._page.run_thread(lambda: self._update_web_status(f"❌ {ex}", DANGER))
            finally:
                self._page.run_thread(self._hide_loading)
        threading.Thread(target=_crawl, daemon=True).start()

    def _set_result(self, title: str, text: str, source_type: str,
                    source_url: str = None, metadata: dict = None):
        """Set input result and show preview."""
        def _apply():
            self._state.title = title
            self._state.source_text = text
            self._state.source_type = source_type
            self._state.source_url = source_url
            self._state.metadata = metadata or {}

            if not self._title_field.value:
                self._title_field.value = title

            # Show preview
            preview_text = text[:2000] + ("..." if len(text) > 2000 else "")
            self._preview.value = preview_text
            self._preview.visible = True

            chars = len(text)
            lines = text.count("\n") + 1
            self._stats_text.value = f"Ký tự: {chars:,} │ Dòng: {lines:,}"

            self._build_controls()
            self._page.update()

        self._page.run_thread(_apply)

    def _update_yt_status(self, msg, color):
        self._yt_status.value = msg
        self._yt_status.color = color
        self._page.update()

    def _update_web_status(self, msg, color):
        self._web_status.value = msg
        self._web_status.color = color
        self._page.update()

    def _hide_loading(self):
        self._loading.visible = False
        self._page.update()

    def _on_next_click(self, e):
        """Validate and go to config tab."""
        # Get text from paste mode if no source_text yet
        if self._mode == 0 and not self._state.source_text:
            text = self._paste_field.value or ""
            if not text.strip():
                show_snackbar(self._page, "Nhập nội dung truyện trước", bgcolor="#EF4444")
                return
            title = self._title_field.value or ""
            from services.input_handler import handle_paste
            result = handle_paste(text.strip(), title.strip())
            self._state.title = result.title
            self._state.source_text = result.text
            self._state.source_type = "paste"

        if not self._state.source_text:
            show_snackbar(self._page, "Chưa có nội dung — chọn nguồn và nhập liệu", bgcolor="#EF4444")
            return

        # Update title from field
        if self._title_field.value:
            self._state.title = self._title_field.value.strip()

        if self._on_next:
            self._on_next()

    def reset(self):
        """Reset input tab."""
        self._paste_field.value = ""
        self._title_field.value = ""
        self._preview.value = ""
        self._preview.visible = False
        self._stats_text.value = ""
        self._yt_url_field.value = ""
        self._web_url_field.value = ""
        self._yt_status.value = ""
        self._web_status.value = ""
        self._mode = 0
        self._mode_buttons = self._build_mode_buttons()
        self._input_area = self._build_input_area()
        self._build_controls()
