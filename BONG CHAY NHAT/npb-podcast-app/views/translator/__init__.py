"""
Translator Tab — Main container with 5 sub-tabs.
Sub-tabs: Nhập liệu | Cấu hình | Phân tích | Tiến trình | Kết quả
"""

import flet as ft
from dataclasses import dataclass, field
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER, BORDER_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT,
    CARD_BORDER_RADIUS, card_style,
)


@dataclass
class TranslatorState:
    """Shared state across all 5 sub-tabs."""
    # Input
    title: str = ""
    source_text: str = ""
    source_type: str = "paste"  # paste / file / youtube / web
    source_url: str = None
    metadata: dict = field(default_factory=dict)

    # Config
    config: dict = field(default_factory=lambda: {
        "genre": "Đời thường",
        "audience": "Người lớn",
        "setting": "Hiện đại",
        "keigo": "casual",
        "narrator": "neutral",
        "style": "podcast",
        "fast_mode": False,
        "channel_name": "にほんのチカラ・【海外の反応】",
        "max_retries": 2,
    })

    # Analyzer output
    analysis: dict = field(default_factory=dict)
    segments: list = field(default_factory=list)  # list of text strings

    # Progress
    translation_id: int = None
    is_running: bool = False

    # Result
    final_text: str = ""
    tts_json: str = ""

    def reset(self):
        """Reset state for new translation."""
        self.title = ""
        self.source_text = ""
        self.source_type = "paste"
        self.source_url = None
        self.metadata = {}
        self.analysis = {}
        self.segments = []
        self.translation_id = None
        self.is_running = False
        self.final_text = ""
        self.tts_json = ""


SUB_TAB_LABELS = ["📥 Nhập liệu", "⚙ Cấu hình", "🔍 Phân tích", "⚡ Tiến trình", "📄 Kết quả"]


class TranslatorView(ft.Column):
    """Main translator tab with sub-tab navigation."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0)
        self._page = page
        self.state = TranslatorState()
        self._active_sub = 0

        # Lazy imports to avoid circular
        from views.translator.tab_input import TabInput
        from views.translator.tab_config import TabConfig
        from views.translator.tab_analysis import TabAnalysis
        from views.translator.tab_progress import TabProgress
        from views.translator.tab_result import TabResult

        self._tabs = [
            TabInput(page, self.state, on_next=lambda: self._switch_sub(1)),
            TabConfig(page, self.state,
                      on_next=lambda: self._switch_sub(2),
                      on_back=lambda: self._switch_sub(0)),
            TabAnalysis(page, self.state,
                        on_next=lambda: self._switch_sub(3),
                        on_back=lambda: self._switch_sub(1)),
            TabProgress(page, self.state,
                        on_complete=lambda: self._switch_sub(4)),
            TabResult(page, self.state,
                      on_new=self._on_new_translation),
        ]

        # Build sub-tab bar
        self._tab_bar = self._build_tab_bar()

        # Content area
        self._content = ft.Container(
            content=self._tabs[0],
            expand=True,
            padding=0,
        )

        self.controls = [self._tab_bar, self._content]

        # Auto-check yt-dlp update
        self._check_ytdlp()

    def _build_tab_bar(self) -> ft.Container:
        """Build sub-tab navigation bar."""
        buttons = []
        for i, label in enumerate(SUB_TAB_LABELS):
            is_active = i == self._active_sub
            buttons.append(
                ft.Container(
                    content=ft.Text(
                        label,
                        size=13,
                        color=ACCENT if is_active else TEXT_MUTED,
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=10),
                    border=ft.border.only(bottom=ft.BorderSide(2, ACCENT if is_active else "transparent")),
                    on_click=lambda e, idx=i: self._on_tab_click(idx),
                    ink=True,
                )
            )

        return ft.Container(
            content=ft.Row(buttons, spacing=0),
            bgcolor=BG_ELEVATED,
            border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
        )

    def _on_tab_click(self, index: int):
        """Handle sub-tab click — only allow forward if data exists."""
        if index == self._active_sub:
            return
        # Tab 4 (Kết quả) always accessible — has its own history
        if index == 4:
            self._switch_sub(index)
            return
        # Allow going back freely
        if index < self._active_sub:
            self._switch_sub(index)
            return
        # Going forward — validate
        if index >= 1 and not self.state.source_text:
            return  # Can't go to config without input
        if index >= 2 and not self.state.config:
            return
        if index >= 3 and not self.state.analysis:
            return  # Can't go to progress without confirmed analysis
        self._switch_sub(index)

    def _switch_sub(self, index: int):
        """Switch to a sub-tab."""
        self._active_sub = index
        self._tab_bar = self._build_tab_bar()
        self._content.content = self._tabs[index]

        # Refresh tab data
        tab = self._tabs[index]
        if hasattr(tab, "refresh"):
            tab.refresh()

        self.controls = [self._tab_bar, self._content]
        self._page.update()

    def _on_new_translation(self):
        """Reset and go to input tab."""
        self.state.reset()
        for tab in self._tabs:
            if hasattr(tab, "reset"):
                tab.reset()
        self._switch_sub(0)

    def _check_ytdlp(self):
        """Auto-check yt-dlp update in background."""
        try:
            from services.ytdlp_manager import check_and_update_async
            check_and_update_async()
        except Exception:
            pass

    def refresh(self):
        """Called when tab becomes active."""
        tab = self._tabs[self._active_sub]
        if hasattr(tab, "refresh"):
            tab.refresh()
