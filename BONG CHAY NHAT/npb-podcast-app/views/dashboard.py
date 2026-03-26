"""
Dashboard Tab — Create new podcast, select format, recent articles.
Supports v1, v2, v3 pipelines.
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

# V3 Writing Styles (from writing_styles.py)
V3_STYLES = [
    ("baseball_jp", "Bóng chày Nhật Bản"),
    ("political", "Phân tích chính trị"),
    ("spy_771", "Tình báo/Ly kỳ (771)"),
    ("crime_jp", "Vụ án - Nhật"),
    ("korea", "Hàn Quốc - Phân tích"),
    ("air_crash", "Air Crash / Mayday"),
    ("storytelling", "Kể chuyện"),
    ("news", "Tin tức / Tài liệu"),
]

V3_HOOKS = [
    ("dramatic", "Mở đầu kịch tính"),
    ("question", "Câu hỏi xoáy sâu"),
    ("shocking", "Sự thật gây sốc"),
    ("promise", "Lời hứa hấp dẫn"),
    ("personal", "Câu chuyện cá nhân"),
]

V3_LANGUAGES = [
    ("vi", "Tiếng Việt"),
    ("en", "Tiếng Anh"),
    ("ja", "Tiếng Nhật"),
    ("ko", "Tiếng Hàn"),
    ("de", "Tiếng Đức"),
    ("fr", "Tiếng Pháp"),
    ("pt", "Tiếng Bồ Đào Nha"),
    ("es", "Tiếng Tây Ban Nha"),
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
            label="Topic / Ý tưởng",
            hint="広島東洋カープ vs 中日ドラゴンズ 開幕戦",
            expand=True,
        )

        # Format cards (v1/v2)
        self.format_cards = ft.Row(wrap=True, spacing=10, run_spacing=10)
        for jp_name, en_name in FORMATS:
            self.format_cards.controls.append(self._format_card(jp_name, en_name))

        # V3 extra fields
        self.v3_channel_input = input_field(label="Tên kênh (CTA)", hint="NPB Channel", expand=True)
        self.v3_style_dd = ft.Dropdown(
            label="Phong cách viết", value="baseball_jp",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in V3_STYLES],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6, expand=True,
        )
        self.v3_hook_dd = ft.Dropdown(
            label="Hook mở đầu", value="dramatic",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in V3_HOOKS],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6, expand=True,
        )
        self.v3_lang_dd = ft.Dropdown(
            label="Ngôn ngữ output", value="ja",
            options=[ft.dropdown.Option(key=k, text=v) for k, v in V3_LANGUAGES],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6, width=180,
        )
        self.v3_duration_input = ft.TextField(
            label="Thời lượng (phút)", hint_text="0 = tự động", value="23", width=120,
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
        )

        self.v3_panel = ft.Container(
            content=ft.Column([
                ft.Text("V3.0 — Viết bài đa phong cách", size=14, weight=ft.FontWeight.W_600, color=ACCENT),
                self.v3_channel_input,
                ft.Row([self.v3_style_dd, self.v3_hook_dd], spacing=12),
                ft.Row([self.v3_lang_dd, self.v3_duration_input], spacing=12),
            ], spacing=12),
            **card_style(),
            visible=False,
        )

        # Format section (v1/v2 only)
        self.format_section = ft.Column([
            ft.Text("Format:", size=14, color=TEXT_SECONDARY),
            self.format_cards,
        ], spacing=8, visible=True)

        # Pipeline version toggle
        self.version_radio = ft.RadioGroup(
            value="v2",
            on_change=self._on_version_change,
            content=ft.Row([
                ft.Radio(value="v1", label="v1 (5 agents)", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY)),
                ft.Radio(value="v2", label="v2 (sections + review)", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_SECONDARY)),
                ft.Radio(value="v3", label="v3.0 (multi-style)", fill_color=ACCENT, label_style=ft.TextStyle(color=TEXT_PRIMARY, weight=ft.FontWeight.W_600)),
            ]),
        )

        # Recent articles
        self.recent_list = ft.Column(spacing=8)
        self._load_recent()

        self.controls = [
            ft.Text("Tạo Podcast Mới", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            # Topic
            self.topic_input,
            # Pipeline version
            ft.Text("Pipeline:", size=14, color=TEXT_SECONDARY),
            self.version_radio,
            # V3 panel (shown when v3 selected)
            self.v3_panel,
            # Format (shown for v1/v2)
            self.format_section,
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
        is_v3 = self.selected_version == "v3"
        self.v3_panel.visible = is_v3
        self.format_section.visible = not is_v3
        self._page.update()

    def _on_start(self, e):
        topic = self.topic_input.value.strip()
        if not topic:
            show_snackbar(self._page, "Vui lòng nhập topic", 2000)
            return

        if self.on_start_pipeline:
            if self.selected_version == "v3":
                # V3: pass extra params via format_type as JSON-encoded string
                import json
                v3_params = json.dumps({
                    "style": self.v3_style_dd.value,
                    "hook": self.v3_hook_dd.value,
                    "language": self.v3_lang_dd.value,
                    "duration": int(self.v3_duration_input.value.strip() or "0"),
                    "channel": self.v3_channel_input.value.strip(),
                }, ensure_ascii=False)
                self.on_start_pipeline(topic, v3_params, "v3")
            else:
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
