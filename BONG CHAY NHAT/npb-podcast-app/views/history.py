"""
History Tab — Browse, search, filter past articles with rich cards.
V3.0 redesign: preview content, titles, pipeline version badges.
"""

import json
import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, WARNING,
    card_style, accent_button, danger_button, outlined_button, input_field, status_badge,
)
from db.models import list_articles, delete_article, get_article

PER_PAGE = 15


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
        self.status_filter = ""
        self.sort_value = "newest"

        self._build()

    def _build(self):
        # Search bar with icon
        self.search_input = ft.TextField(
            hint_text="Tìm kiếm topic...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
            border_color=BORDER, focused_border_color=ACCENT, border_radius=8,
            expand=True, on_change=self._on_search_change,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        # Compact filters
        self.status_dropdown = ft.Dropdown(
            value="",
            options=[
                ft.dropdown.Option("", "Tất cả"),
                ft.dropdown.Option("completed", "Hoàn tất"),
                ft.dropdown.Option("failed", "Lỗi"),
            ],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=120, on_select=self._on_filter_change,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        self.sort_dropdown = ft.Dropdown(
            value="newest",
            options=[
                ft.dropdown.Option("newest", "Mới nhất"),
                ft.dropdown.Option("oldest", "Cũ nhất"),
                ft.dropdown.Option("duration", "Lâu nhất"),
            ],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=120, on_select=self._on_filter_change,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        # Article list
        self.article_list = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

        # Pagination
        self.page_info = ft.Text("", size=12, color=TEXT_MUTED)
        self.prev_btn = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_size=20, icon_color=TEXT_SECONDARY, on_click=self._prev_page)
        self.next_btn = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_size=20, icon_color=TEXT_SECONDARY, on_click=self._next_page)
        self.page_label = ft.Text("1", size=13, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600)

        self.controls = [
            # Header
            ft.Row([
                ft.Text("Lịch sử", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(expand=True),
                self.page_info,
            ]),
            # Search + filters
            ft.Row([
                self.search_input,
                self.status_dropdown,
                self.sort_dropdown,
            ], spacing=8),
            # Articles
            self.article_list,
            # Pagination
            ft.Row([
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
                        ft.Icon(ft.Icons.HISTORY_ROUNDED, size=48, color=TEXT_MUTED),
                        ft.Text("Chưa có bài viết nào", size=14, color=TEXT_MUTED),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.Alignment(0, 0),
                    padding=60,
                )
            )
        else:
            for a in articles:
                self.article_list.controls.append(self._article_card(a))

        self.page_info.value = f"{total} bài viết"
        self.page_label.value = f"{self.current_page}/{total_pages}"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= total_pages

        self._page.update()

    def _article_card(self, article: dict) -> ft.Container:
        """Build a rich card for one article."""
        status = article.get("run_status", "completed") or "completed"
        total_time = article.get("total_time")
        created = (article.get("created_at") or "")[:16].replace("T", " ")
        article_id = article["id"]
        content = article.get("content", "")
        titles_raw = article.get("titles", "")
        fmt = article.get("format", "")

        # Status badge
        if status == "completed":
            status_ctl = ft.Container(
                content=ft.Text("OK", size=10, color="#fff", weight=ft.FontWeight.BOLD),
                bgcolor=SUCCESS, border_radius=4,
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
            )
        else:
            status_ctl = ft.Container(
                content=ft.Text("FAIL", size=10, color="#fff", weight=ft.FontWeight.BOLD),
                bgcolor=DANGER, border_radius=4,
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
            )

        # Time badge
        if total_time:
            m = int(total_time // 60)
            s = int(total_time % 60)
            time_ctl = ft.Text(f"{m}:{s:02d}", size=11, color=TEXT_MUTED)
        else:
            time_ctl = ft.Text("—", size=11, color=TEXT_MUTED)

        # Content preview (first 120 chars)
        preview = ""
        if content:
            preview = content[:120].replace("\n", " ").strip()
            if len(content) > 120:
                preview += "..."

        # Title preview (first title if available)
        title_preview = None
        if titles_raw:
            try:
                titles = json.loads(titles_raw)
                if titles:
                    title_preview = titles[0]
            except (json.JSONDecodeError, TypeError):
                pass

        # Format badge
        fmt_short = fmt[:12] if fmt else ""

        # Action buttons row
        actions = []
        if titles_raw:
            actions.append(ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.TITLE_ROUNDED, size=14, color=ACCENT),
                    ft.Text("Titles", size=11, color=ACCENT),
                ], spacing=4, tight=True),
                on_click=lambda e, tr=titles_raw: self._show_titles(tr),
            ))
        if status == "completed":
            actions.append(ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.COPY_ROUNDED, size=14, color=TEXT_SECONDARY),
                    ft.Text("Copy", size=11, color=TEXT_SECONDARY),
                ], spacing=4, tight=True),
                on_click=lambda e, aid=article_id: self._copy_article(aid),
            ))
        actions.append(ft.TextButton(
            content=ft.Row([
                ft.Icon(ft.Icons.EDIT_ROUNDED, size=14, color=TEXT_SECONDARY),
                ft.Text("Edit", size=11, color=TEXT_SECONDARY),
            ], spacing=4, tight=True),
            on_click=lambda e, aid=article_id: self._edit_article(aid),
        ))
        actions.append(ft.TextButton(
            content=ft.Row([
                ft.Icon(ft.Icons.REPLAY_ROUNDED, size=14, color=TEXT_SECONDARY),
                ft.Text("Rerun", size=11, color=TEXT_SECONDARY),
            ], spacing=4, tight=True),
            on_click=lambda e, t=article["topic"], f=fmt: self._rerun(t, f),
        ))
        actions.append(ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=TEXT_MUTED,
            tooltip="Xóa", on_click=lambda e, aid=article_id: self._delete_article(aid),
        ))

        # Build card
        card_content = [
            # Row 1: Status + Topic + Time + Date
            ft.Row([
                status_ctl,
                ft.Text(article["topic"][:60], size=14, color=TEXT_PRIMARY,
                        weight=ft.FontWeight.W_600, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                time_ctl,
                ft.Text(created, size=11, color=TEXT_MUTED),
            ], spacing=8),
        ]

        # Row 2: Title preview (if available)
        if title_preview:
            card_content.append(
                ft.Row([
                    ft.Icon(ft.Icons.TITLE_ROUNDED, size=12, color=ACCENT),
                    ft.Text(title_preview, size=12, color=ACCENT, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, expand=True, italic=True),
                ], spacing=4),
            )

        # Row 3: Content preview
        if preview:
            card_content.append(
                ft.Text(preview, size=12, color=TEXT_MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            )

        # Row 4: Format badge + Actions
        card_content.append(
            ft.Row([
                ft.Container(
                    content=ft.Text(fmt_short, size=10, color=TEXT_SECONDARY),
                    bgcolor=BG_ELEVATED, border_radius=4,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                ) if fmt_short else ft.Container(),
                ft.Container(expand=True),
                *actions,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        return ft.Container(
            content=ft.Column(card_content, spacing=6),
            padding=ft.padding.all(14),
            bgcolor=BG_CARD,
            border=ft.border.all(1, BORDER),
            border_radius=10,
        )

    def _on_search_change(self, e):
        self.search_value = e.control.value
        self.current_page = 1
        self._load_articles()

    def _on_filter_change(self, e):
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

    def _show_titles(self, titles_raw: str):
        """Show titles dialog with copy all button."""
        try:
            titles = json.loads(titles_raw)
        except (json.JSONDecodeError, TypeError):
            titles = []

        if not titles:
            show_snackbar(self._page, "Không có tiêu đề", 2000)
            return

        all_titles_text = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))

        title_rows = []
        for i, title in enumerate(titles, 1):
            title_rows.append(
                ft.Text(f"{i}. {title}", size=13, color=TEXT_PRIMARY, selectable=True),
            )

        def on_copy_all(e):
            self._page.run_task(ft.Clipboard().set, all_titles_text)
            show_snackbar(self._page, f"Đã copy {len(titles)} tiêu đề", 1500)

        def on_close(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Tiêu đề gợi ý", size=16, weight=ft.FontWeight.W_600),
            content=ft.Column(title_rows, spacing=8, width=500),
            actions=[
                ft.TextButton("Copy tất cả", on_click=on_copy_all),
                ft.TextButton("Đóng", on_click=on_close),
            ],
        )
        show_dialog(self._page, dialog)

    def _copy_article(self, article_id: int):
        a = get_article(article_id)
        if a:
            self._page.run_task(ft.Clipboard().set, a["content"])
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
