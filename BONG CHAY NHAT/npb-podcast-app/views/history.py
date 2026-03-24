"""
History Tab — Browse, search, filter, paginate past articles.
"""

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, WARNING,
    card_style, accent_button, danger_button, outlined_button, input_field, status_badge,
)
from db.models import list_articles, delete_article, get_article

FORMATS_ALL = [
    "", "試合プレビュー", "週間まとめ", "パワーランキング",
    "チーム深掘り分析", "選手スポットライト", "戦術ブレイクダウン",
    "ポストシーズン予測", "初心者向け解説",
]

PER_PAGE = 20


class HistoryTab(ft.Column):
    """History — browse and manage past articles."""

    def __init__(self, page: ft.Page, on_edit=None, on_rerun=None):
        super().__init__(expand=True, spacing=12)
        self._page = page
        self.on_edit = on_edit
        self.on_rerun = on_rerun

        self.current_page = 1
        self.total_count = 0
        self.search_value = ""
        self.format_filter = ""
        self.status_filter = ""
        self.sort_value = "newest"

        self._build()

    def _build(self):
        # Search bar
        self.search_input = input_field(hint="Tìm kiếm topic...", expand=True, on_change=self._on_search_change)

        # Filters
        self.format_dropdown = ft.Dropdown(
            label="Format",
            value="",
            options=[ft.dropdown.Option(f, f if f else "Tất cả") for f in FORMATS_ALL],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=180, on_select=self._on_filter_change,
        )

        self.status_dropdown = ft.Dropdown(
            label="Status",
            value="",
            options=[
                ft.dropdown.Option("", "Tất cả"),
                ft.dropdown.Option("completed", "Completed"),
                ft.dropdown.Option("failed", "Failed"),
            ],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=150, on_select=self._on_filter_change,
        )

        self.sort_dropdown = ft.Dropdown(
            label="Sort",
            value="newest",
            options=[
                ft.dropdown.Option("newest", "Mới nhất"),
                ft.dropdown.Option("oldest", "Cũ nhất"),
                ft.dropdown.Option("duration", "Thời gian chạy"),
            ],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=150, on_select=self._on_filter_change,
        )

        # Article list
        self.article_list = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

        # Pagination
        self.page_info = ft.Text("", size=12, color=TEXT_MUTED)
        self.prev_btn = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=TEXT_SECONDARY, on_click=self._prev_page)
        self.next_btn = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=TEXT_SECONDARY, on_click=self._next_page)
        self.page_label = ft.Text("1", size=13, color=TEXT_PRIMARY)

        self.controls = [
            ft.Text("Lịch sử bài viết", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            self.search_input,
            ft.Row([self.format_dropdown, self.status_dropdown, self.sort_dropdown], spacing=12),
            self.article_list,
            ft.Row([
                self.page_info,
                ft.Container(expand=True),
                self.prev_btn,
                self.page_label,
                self.next_btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]

        self._load_articles()

    def _load_articles(self):
        """Load articles from DB with current filters."""
        articles, total = list_articles(
            search=self.search_value,
            format_filter=self.format_filter,
            status_filter=self.status_filter,
            sort=self.sort_value,
            page=self.current_page,
            per_page=PER_PAGE,
        )
        self.total_count = total
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

        self.article_list.controls.clear()

        if not articles:
            self.article_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=48, color=TEXT_MUTED),
                        ft.Text("Không có bài viết nào", size=14, color=TEXT_MUTED),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.Alignment(0, 0),
                    padding=40,
                )
            )
        else:
            for a in articles:
                self.article_list.controls.append(self._article_card(a))

        self.page_info.value = f"Tổng: {total} bài"
        self.page_label.value = f"{self.current_page} / {total_pages}"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= total_pages

        self._page.update()

    def _article_card(self, article: dict) -> ft.Container:
        """Build a card for one article."""
        status = article.get("run_status", "completed") or "completed"
        status_icon = "✅" if status == "completed" else "❌"
        total_time = article.get("total_time")
        time_str = f"{int(total_time // 60)}:{int(total_time % 60):02d}" if total_time else "—"
        created = (article.get("created_at") or "")[:16]
        article_id = article["id"]

        # Action buttons
        actions = []
        if status == "completed":
            actions.append(ft.IconButton(
                icon=ft.Icons.COPY_ROUNDED, icon_size=18, icon_color=TEXT_MUTED,
                tooltip="Copy", on_click=lambda e, aid=article_id: self._copy_article(aid),
            ))
        else:
            actions.append(ft.IconButton(
                icon=ft.Icons.LIST_ALT_ROUNDED, icon_size=18, icon_color=TEXT_MUTED,
                tooltip="Logs",
            ))

        actions.extend([
            ft.IconButton(
                icon=ft.Icons.EDIT_ROUNDED, icon_size=18, icon_color=TEXT_MUTED,
                tooltip="Edit", on_click=lambda e, aid=article_id: self._edit_article(aid),
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_ROUNDED, icon_size=18, icon_color=TEXT_MUTED,
                tooltip="Xóa", on_click=lambda e, aid=article_id: self._delete_article(aid),
            ),
            ft.IconButton(
                icon=ft.Icons.REPLAY_ROUNDED, icon_size=18, icon_color=TEXT_MUTED,
                tooltip="Run lại",
                on_click=lambda e, t=article["topic"], f=article["format"]: self._rerun(t, f),
            ),
        ])

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"{status_icon}  {article['topic'][:50]}", size=14, color=TEXT_PRIMARY,
                            weight=ft.FontWeight.W_600, expand=True),
                    ft.Text(time_str, size=12, color=TEXT_MUTED),
                    ft.Text(created, size=12, color=TEXT_MUTED),
                ], spacing=12),
                ft.Row([
                    ft.Text(article["format"], size=12, color=TEXT_SECONDARY),
                    ft.Container(expand=True),
                    *actions,
                ], spacing=4),
            ], spacing=4),
            padding=12,
            bgcolor=BG_CARD,
            border=ft.border.all(1, BORDER),
            border_radius=8,
        )

    def _on_search_change(self, e):
        self.search_value = e.control.value
        self.current_page = 1
        self._load_articles()

    def _on_filter_change(self, e):
        self.format_filter = self.format_dropdown.value or ""
        self.status_filter = self.status_dropdown.value or ""
        self.sort_value = self.sort_dropdown.value or "newest"
        self.current_page = 1
        self._load_articles()

    def _prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self._load_articles()

    def _next_page(self, e):
        total_pages = max(1, (self.total_count + PER_PAGE - 1) // PER_PAGE)
        if self.current_page < total_pages:
            self.current_page += 1
            self._load_articles()

    def _copy_article(self, article_id: int):
        a = get_article(article_id)
        if a:
            self._page.set_clipboard(a["content"])
            show_snackbar(self._page, "Đã copy nội dung", 2000)

    def _edit_article(self, article_id: int):
        if self.on_edit:
            self.on_edit(article_id)

    def _delete_article(self, article_id: int):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            delete_article(article_id)
            self._load_articles()
            show_snackbar(self._page, "Đã xóa", 2000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Xóa bài viết?"),
            content=ft.Text("Bài viết và logs liên quan sẽ bị xóa vĩnh viễn."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Xóa"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _rerun(self, topic: str, format_type: str):
        if self.on_rerun:
            self.on_rerun(topic, format_type)

    def refresh(self):
        self._load_articles()
