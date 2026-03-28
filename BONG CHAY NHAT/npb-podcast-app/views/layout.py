"""
Main Layout — Sidebar (icon-based) + Content area + Status bar.
"""

import flet as ft
from theme import (
    BG_PRIMARY, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SIDEBAR_WIDTH, SUCCESS,
)
from services.updater import get_current_version


class SidebarItem:
    def __init__(self, icon: str, label: str, index: int):
        self.icon = icon
        self.label = label
        self.index = index


SIDEBAR_ITEMS_TOP = [
    SidebarItem(ft.Icons.HOME_ROUNDED, "Dashboard", 0),
    SidebarItem(ft.Icons.PLAY_CIRCLE_ROUNDED, "Pipeline", 1),
    SidebarItem(ft.Icons.LIST_ALT_ROUNDED, "Lịch sử", 2),
    SidebarItem(ft.Icons.EDIT_NOTE_ROUNDED, "Editor", 3),
]

SIDEBAR_ITEMS_BOTTOM_GROUP = [
    SidebarItem(ft.Icons.TRANSLATE_ROUNDED, "Dịch Truyện", 4),
    SidebarItem(ft.Icons.RECORD_VOICE_OVER_ROUNDED, "Voice TTS", 5),
]

SETTINGS_ITEM = SidebarItem(ft.Icons.SETTINGS_ROUNDED, "Cấu hình", 6)
LICENSE_ITEM = SidebarItem(ft.Icons.KEY_ROUNDED, "License", 7)

# Keep SIDEBAR_ITEMS for backward compat (all nav items)
SIDEBAR_ITEMS = SIDEBAR_ITEMS_TOP + SIDEBAR_ITEMS_BOTTOM_GROUP + [SETTINGS_ITEM]


class MainLayout(ft.Column):
    """Main app layout with sidebar + content + status bar."""

    def __init__(self, page: ft.Page, views: list, on_tab_change=None):
        super().__init__(expand=True, spacing=0)
        self._page = page
        self.views = views
        self.on_tab_change_callback = on_tab_change
        self.active_index = 0
        self._update_badge_visible = False

        # Build sidebar
        self.sidebar = self._build_sidebar()

        # Content container
        self.content_area = ft.Container(
            content=self.views[0] if self.views else ft.Text(""),
            expand=True,
            bgcolor=BG_PRIMARY,
            padding=24,
        )

        # Status bar
        self.status_text = ft.Text("", size=12, color=TEXT_MUTED)
        self.version_text = ft.Text(f"v{get_current_version()}", size=12, color=TEXT_MUTED)
        self.license_status = ft.Text("", size=12, color=SUCCESS)

        self.status_bar = ft.Container(
            content=ft.Row(
                [
                    self.license_status,
                    ft.VerticalDivider(width=1, color=BORDER),
                    self.version_text,
                    ft.VerticalDivider(width=1, color=BORDER),
                    self.status_text,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=BG_ELEVATED,
            border=ft.border.only(top=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(horizontal=16, vertical=6),
            height=32,
        )

        # Compose layout
        body = ft.Row(
            [self.sidebar, self.content_area],
            expand=True,
            spacing=0,
        )

        self.controls = [body, self.status_bar]

    def _build_sidebar(self) -> ft.Container:
        """Build icon sidebar."""
        # Top group: NPB podcast tabs
        top_buttons = [self._sidebar_button(item) for item in SIDEBAR_ITEMS_TOP]

        # Bottom group: Translator
        translator_buttons = [self._sidebar_button(item) for item in SIDEBAR_ITEMS_BOTTOM_GROUP]

        # Settings
        settings_btn = self._sidebar_button(SETTINGS_ITEM)

        # License button at bottom
        license_btn = self._sidebar_button(LICENSE_ITEM)

        sidebar_col = ft.Column(
            [
                # App icon/title area
                ft.Container(
                    content=ft.Text("NPB", size=14, weight=ft.FontWeight.BOLD, color=ACCENT, text_align=ft.TextAlign.CENTER),
                    height=48,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Divider(height=1, color=BORDER),
                # Top nav items (Dashboard, Pipeline, History, Editor)
                ft.Column(top_buttons, spacing=4),
                # Divider between groups
                ft.Container(
                    content=ft.Divider(height=1, color=BORDER),
                    margin=ft.margin.symmetric(vertical=4, horizontal=8),
                ),
                # Translator group
                ft.Column(translator_buttons, spacing=4, expand=True),
                # Bottom system items
                ft.Divider(height=1, color=BORDER),
                settings_btn,
                license_btn,
            ],
            spacing=0,
            expand=True,
        )

        return ft.Container(
            content=sidebar_col,
            width=SIDEBAR_WIDTH,
            bgcolor=BG_ELEVATED,
            border=ft.border.only(right=ft.BorderSide(1, BORDER)),
            padding=ft.padding.symmetric(vertical=8, horizontal=4),
        )

    def _sidebar_button(self, item: SidebarItem) -> ft.Container:
        """Create a single sidebar icon button."""
        is_active = item.index == self.active_index
        icon_color = ACCENT if is_active else TEXT_MUTED
        left_border = ft.border.only(left=ft.BorderSide(3, ACCENT)) if is_active else None

        icon_btn = ft.IconButton(
            icon=item.icon,
            icon_color=icon_color,
            icon_size=22,
            tooltip=item.label,
            on_click=lambda e, idx=item.index: self._on_nav_click(idx),
        )

        # Show update badge on License tab
        show_badge = (item.index == LICENSE_ITEM.index and self._update_badge_visible)
        if show_badge:
            content = ft.Stack([
                icon_btn,
                ft.Container(
                    width=8, height=8,
                    bgcolor="#EF4444",
                    border_radius=4,
                    top=6, right=6,
                ),
            ], width=44, height=44)
        else:
            content = icon_btn

        btn = ft.Container(
            content=content,
            border=left_border,
            border_radius=4,
            height=44,
            alignment=ft.Alignment(0, 0),
        )
        return btn

    def _on_nav_click(self, index: int):
        """Handle sidebar navigation click."""
        if index == self.active_index:
            return
        self.active_index = index
        if index < len(self.views):
            self.content_area.content = self.views[index]
            # Auto-refresh tab data when switching to it
            view = self.views[index]
            if hasattr(view, "refresh"):
                view.refresh()

        # Rebuild sidebar to update active state
        self.sidebar.content = self._build_sidebar().content
        self._page.update()

        if self.on_tab_change_callback:
            self.on_tab_change_callback(index)

    def switch_to(self, index: int):
        """Programmatically switch to a tab."""
        self._on_nav_click(index)

    def set_status(self, text: str):
        self.status_text.value = text
        self._page.update()

    def set_license_status(self, text: str, valid: bool = True):
        self.license_status.value = text
        self.license_status.color = SUCCESS if valid else TEXT_MUTED
        self._page.update()

    def set_update_badge(self, visible: bool):
        """Show/hide update available badge on License sidebar icon."""
        if self._update_badge_visible == visible:
            return
        self._update_badge_visible = visible
        self.sidebar.content = self._build_sidebar().content
        self._page.update()
