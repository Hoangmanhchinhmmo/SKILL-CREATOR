"""
Dashboard Tab — Create new podcast, select format, recent articles.
"""

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, BORDER_HOVER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS,
    card_style, accent_button, input_field,
)
from db.models import get_recent_articles

# Format options matching config.py FORMATS
FORMATS = [
    ("試合プレビュー", "Match Preview"),
    ("週間まとめ", "Weekly Wrap"),
    ("パワーランキング", "Power Rankings"),
    ("チーム深掘り分析", "Team Deep Dive"),
    ("選手スポットライト", "Player Spotlight"),
    ("戦術ブレイクダウン", "Tactical Breakdown"),
    ("ポストシーズン予測", "Postseason Prediction"),
    ("初心者向け解説", "Beginner Guide"),
]


class DashboardTab(ft.Column):
    """Dashboard — create new podcast script."""

    def __init__(self, page: ft.Page, on_start_pipeline=None):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.on_start_pipeline = on_start_pipeline
        self.selected_format = FORMATS[0][0]
        self.selected_version = "v2"
        self._build()

    def _build(self):
        # Topic input
        self.topic_input = input_field(
            label="Topic",
            hint="広島東洋カープ vs 中日ドラゴンズ 開幕戦",
            expand=True,
        )

        # Format cards
        self.format_cards = ft.Row(
            wrap=True,
            spacing=10,
            run_spacing=10,
        )
        for jp_name, en_name in FORMATS:
            self.format_cards.controls.append(self._format_card(jp_name, en_name))

        # Pipeline version toggle
        self.version_radio = ft.RadioGroup(
            value="v2",
            on_change=self._on_version_change,
            content=ft.Row([
                ft.Radio(value="v1", label="v1 (5 agents)", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY)),
                ft.Radio(value="v2", label="v2 (6 sections + supervisor)", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY)),
            ]),
        )

        # Recent articles
        self.recent_list = ft.Column(spacing=8)
        self._load_recent()

        self.controls = [
            ft.Text("Tạo Podcast Mới", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            # Topic
            self.topic_input,
            # Format
            ft.Text("Format:", size=14, color=TEXT_SECONDARY),
            self.format_cards,
            # Pipeline version
            ft.Text("Pipeline:", size=14, color=TEXT_SECONDARY),
            self.version_radio,
            # Start button
            ft.Container(height=8),
            ft.Row(
                [accent_button("BẮT ĐẦU TẠO", icon=ft.Icons.PLAY_ARROW_ROUNDED, on_click=self._on_start, width=220)],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            # Recent articles
            ft.Container(height=16),
            ft.Divider(color=BORDER),
            ft.Text("Bài viết gần đây", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            self.recent_list,
        ]

    def _format_card(self, jp_name: str, en_name: str) -> ft.Container:
        """Create a selectable format card."""
        is_selected = jp_name == self.selected_format
        border_color = ACCENT if is_selected else BORDER

        return ft.Container(
            content=ft.Column([
                ft.Text(jp_name, size=13, color=TEXT_PRIMARY if is_selected else TEXT_SECONDARY, weight=ft.FontWeight.W_600),
                ft.Text(en_name, size=11, color=TEXT_MUTED),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=150,
            padding=12,
            bgcolor=BG_CARD if not is_selected else BG_ELEVATED,
            border=ft.border.all(2 if is_selected else 1, border_color),
            border_radius=8,
            on_click=lambda e, name=jp_name: self._select_format(name),
            ink=True,
        )

    def _select_format(self, format_name: str):
        self.selected_format = format_name
        # Rebuild format cards
        self.format_cards.controls.clear()
        for jp_name, en_name in FORMATS:
            self.format_cards.controls.append(self._format_card(jp_name, en_name))
        self._page.update()

    def _on_version_change(self, e):
        self.selected_version = e.control.value

    def _on_start(self, e):
        topic = self.topic_input.value.strip()
        if not topic:
            show_snackbar(self._page, "Vui lòng nhập topic", 2000)
            return

        if self.on_start_pipeline:
            self.on_start_pipeline(topic, self.selected_format, self.selected_version)

    def _load_recent(self):
        """Load recent articles from SQLite."""
        articles = get_recent_articles(5)
        self.recent_list.controls.clear()

        if not articles:
            self.recent_list.controls.append(
                ft.Text("Chưa có bài viết nào", size=13, color=TEXT_MUTED, italic=True),
            )
            return

        for a in articles:
            status = a.get("run_status", "completed")
            status_icon = "✅" if status == "completed" else "❌"
            time_str = self._format_time(a.get("total_time"))
            created = a.get("created_at", "")[:16]

            self.recent_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(f"{status_icon}  {a['topic'][:40]}", size=13, color=TEXT_PRIMARY, expand=True),
                        ft.Text(a["format"], size=12, color=TEXT_MUTED),
                        ft.Text(time_str, size=12, color=TEXT_MUTED, width=60),
                        ft.Text(created, size=12, color=TEXT_MUTED, width=120),
                    ], spacing=12),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    bgcolor=BG_CARD,
                    border=ft.border.all(1, BORDER),
                    border_radius=6,
                )
            )

    def _format_time(self, seconds) -> str:
        if not seconds:
            return ""
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def refresh(self):
        """Refresh recent articles list."""
        self._load_recent()
        self._page.update()
