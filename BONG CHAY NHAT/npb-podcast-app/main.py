"""
NPB Podcast Writer — Flet Desktop App
Entry point: python main.py
"""

import os
import sys

# Fix Flet desktop runtime path for packaged builds
# flet pack (PyInstaller) handles this automatically, but we keep a fallback
# for onedir builds where the runtime may be in a subdirectory
if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    for _candidate in [
        os.path.join(getattr(sys, "_MEIPASS", ""), "flet_desktop", "app", "flet"),  # flet pack (auto)
        os.path.join(_exe_dir, "flet_desktop", "app", "flet"),  # onedir fallback
        os.path.join(_exe_dir, "runtime", "flet"),               # manual copy fallback
    ]:
        if os.path.isdir(_candidate) and os.path.exists(os.path.join(_candidate, "flet.exe")):
            os.environ["FLET_VIEW_PATH"] = _candidate
            break

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_PRIMARY, ACCENT, TEXT_PRIMARY,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    get_theme,
)
from db.database import init_db
from services import license_service
from services.updater import check_for_update, download_and_install
from views.layout import MainLayout
from views.license import FirstLaunchView, LicenseTab
from views.dashboard import DashboardTab
from views.pipeline import PipelineTab
from views.history import HistoryTab
from views.editor import EditorTab
from views.translator import TranslatorView
from views.settings import SettingsTab


def main(page: ft.Page):
    # === Window config ===
    page.title = "NPB Podcast Writer"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = get_theme()
    page.bgcolor = BG_PRIMARY
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.min_width = WINDOW_MIN_WIDTH
    page.window.min_height = WINDOW_MIN_HEIGHT
    page.padding = 0
    page.spacing = 0

    # === Init database ===
    init_db()

    # === App state ===
    app_state = {
        "current_article_id": None,
        "current_run_id": None,
    }

    # === Tab references (built lazily after license check) ===
    layout: MainLayout | None = None

    def build_main_app():
        """Build the main app UI after license is verified."""
        nonlocal layout

        # Create tab views
        dashboard = DashboardTab(page, on_start_pipeline=on_start_pipeline)
        pipeline_tab = PipelineTab(page, on_open_editor=on_open_editor)
        history = HistoryTab(page, on_edit=on_edit_article, on_rerun=on_rerun_article)
        editor = EditorTab(page)
        translator = TranslatorView(page)
        settings = SettingsTab(page)
        def on_update_available(available: bool):
            if layout:
                layout.set_update_badge(available)

        license_tab = LicenseTab(page, on_deactivated=on_deactivated, on_update_available=on_update_available)

        views = [dashboard, pipeline_tab, history, editor, translator, settings, license_tab]

        layout = MainLayout(page, views)

        # Set license status
        info = license_service.get_license_info()
        if info:
            plan = info.get("plan", "Licensed")
            layout.set_license_status(f"● {plan}", valid=True)

        page.controls.clear()
        page.add(layout)
        page.update()

        # Check for updates in background
        _check_updates_silent()

    def on_start_pipeline(topic: str, format_type: str, pipeline_version: str):
        """Called when user clicks 'Bắt đầu tạo' on Dashboard."""
        if layout:
            # Switch to Pipeline tab
            layout.switch_to(1)
            # Get pipeline tab and start
            pipeline_tab = layout.views[1]
            pipeline_tab.start(topic, format_type, pipeline_version, app_state)

    def on_open_editor(article_id: int):
        """Called when pipeline finishes — open editor with result."""
        if layout:
            app_state["current_article_id"] = article_id
            editor_tab = layout.views[3]
            editor_tab.load_article(article_id)
            layout.switch_to(3)

    def on_edit_article(article_id: int):
        """Called from History tab to edit an article."""
        on_open_editor(article_id)

    def on_rerun_article(topic: str, format_type: str):
        """Called from History tab to re-run pipeline."""
        on_start_pipeline(topic, format_type, "v2")

    def on_deactivated():
        """Called when user deactivates license."""
        show_first_launch()

    def show_first_launch():
        """Show the first-launch activation screen."""
        page.controls.clear()
        first_launch = FirstLaunchView(page, on_activated=build_main_app)
        page.add(first_launch)
        page.update()

    def _check_updates_silent():
        """Check for updates silently on startup."""
        try:
            update = check_for_update()
            if update and update.get("required"):
                def on_update(e):
                    close_dialog(page, dialog)
                    download_and_install(update["download_url"])
                    page.window.close()

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(f"Bắt buộc cập nhật v{update['version']}"),
                    content=ft.Text(update.get("changelog", "")),
                    actions=[
                        ft.TextButton(content=ft.Text("Cập nhật ngay"), style=ft.ButtonStyle(color=ACCENT), on_click=on_update),
                    ],
                )
                show_dialog(page, dialog)
        except Exception:
            pass

    # === Startup: Check license ===
    # DEV MODE: Set to True to bypass license check for UI testing
    DEV_BYPASS_LICENSE = False

    if DEV_BYPASS_LICENSE:
        build_main_app()
        layout.set_license_status("● DEV MODE", valid=True)
    else:
        # Show loading while checking license
        loading_view = ft.Column(
            [
                ft.Container(height=200),
                ft.Icon(ft.Icons.PODCASTS_ROUNDED, size=64, color=ACCENT),
                ft.Text("NPB Podcast Writer", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(height=20),
                ft.ProgressRing(width=30, height=30, stroke_width=3, color=ACCENT),
                ft.Text("Đang kiểm tra license...", size=13, color="#A1A1AA"),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
        )
        page.add(loading_view)
        page.update()

        import threading

        def _check_license():
            result = license_service.check_on_startup()

            def _apply():
                page.controls.clear()
                page.update()
                if result.get("needs_activation"):
                    show_first_launch()
                else:
                    build_main_app()
                    if result.get("grace"):
                        show_snackbar(page, f"⚠ {result['message']}", 5000, "#EAB308")

            page.run_thread(_apply)

        threading.Thread(target=_check_license, daemon=True).start()


ft.run(main)
