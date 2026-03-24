"""
Settings Tab — API keys, model selection, pipeline config, storage management.
"""

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, SUCCESS, DANGER,
    card_style, accent_button, danger_button, outlined_button, input_field,
)
from db.models import get_setting, set_setting, get_all_settings, get_article_count, get_log_count, delete_old_logs
from db.database import get_db_size
from services.machine_id import get_machine_code
from services.crypto import encrypt, decrypt

GEMINI_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]

# Setting keys
KEY_WRITER = "gemini_key_writer"
KEY_EDITOR = "gemini_key_editor"
KEY_ARCHITECT = "gemini_key_architect"
MODEL_DATA = "model_data"
MODEL_ANALYSIS = "model_analysis"
MODEL_WRITER = "model_writer"
MODEL_SUPERVISOR = "model_supervisor"
TEMPERATURE = "temperature"
SUPERVISOR_TEMP = "supervisor_temperature"
MAX_TOKENS = "max_output_tokens"
MAX_RETRIES = "max_retries"
LICENSE_URL = "license_server_url"
UPDATE_URL = "update_server_url"


class SettingsTab(ft.Column):
    """Settings configuration view."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.machine_code = get_machine_code()
        self._build()

    def _build(self):
        # Load current settings
        self._load_values()

        # API Keys section
        self.key_writer_input = input_field(label="Gemini Key (Writer)", password=True, value=self.vals.get(KEY_WRITER, ""), expand=True)
        self.key_editor_input = input_field(label="Gemini Key (Editor)", password=True, value=self.vals.get(KEY_EDITOR, ""), expand=True)
        self.key_architect_input = input_field(label="Gemini Key (Architect)", password=True, value=self.vals.get(KEY_ARCHITECT, ""), expand=True)

        # Model dropdowns
        self.model_data_dd = self._model_dropdown("Data Collector", self.vals.get(MODEL_DATA, "gemini-2.5-pro"))
        self.model_analysis_dd = self._model_dropdown("Tactical Analyst", self.vals.get(MODEL_ANALYSIS, "gemini-2.5-pro"))
        self.model_writer_dd = self._model_dropdown("Section Writer", self.vals.get(MODEL_WRITER, "gemini-2.5-pro"))
        self.model_supervisor_dd = self._model_dropdown("Supervisor", self.vals.get(MODEL_SUPERVISOR, "gemini-2.5-pro"))

        # Pipeline sliders
        temp_val = float(self.vals.get(TEMPERATURE, "0.8"))
        sup_temp_val = float(self.vals.get(SUPERVISOR_TEMP, "0.3"))

        self.temp_label = ft.Text(f"{temp_val:.1f}", size=13, color=TEXT_PRIMARY, width=35)
        self.temp_slider = ft.Slider(
            min=0, max=1, value=temp_val, divisions=10,
            active_color=ACCENT, label="{value}",
            on_change=lambda e: self._on_slider(e, self.temp_label),
            expand=True,
        )

        self.sup_temp_label = ft.Text(f"{sup_temp_val:.1f}", size=13, color=TEXT_PRIMARY, width=35)
        self.sup_temp_slider = ft.Slider(
            min=0, max=1, value=sup_temp_val, divisions=10,
            active_color=ACCENT, label="{value}",
            on_change=lambda e: self._on_slider(e, self.sup_temp_label),
            expand=True,
        )

        self.tokens_input = input_field(label="Max Output Tokens", value=self.vals.get(MAX_TOKENS, "16384"))
        self.retries_input = input_field(label="Max Retries", value=self.vals.get(MAX_RETRIES, "2"))


        # Storage info
        db_size_mb = get_db_size() / (1024 * 1024)
        article_count = get_article_count()
        log_count = get_log_count()

        # Save message
        self.save_msg = ft.Text("", size=12)

        self.controls = [
            ft.Text("Cấu hình", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),

            # API Keys
            self._section_header("API Keys"),
            ft.Container(
                content=ft.Column([
                    self._key_row(self.key_writer_input),
                    self._key_row(self.key_editor_input),
                    self._key_row(self.key_architect_input),
                ], spacing=12),
                **card_style(),
            ),

            # Model
            self._section_header("Model"),
            ft.Container(
                content=ft.Column([
                    self.model_data_dd,
                    self.model_analysis_dd,
                    self.model_writer_dd,
                    self.model_supervisor_dd,
                ], spacing=12),
                **card_style(),
            ),

            # Pipeline
            self._section_header("Pipeline"),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text("Temperature:", size=13, color=TEXT_SECONDARY, width=180), self.temp_slider, self.temp_label]),
                    ft.Row([ft.Text("Supervisor Temperature:", size=13, color=TEXT_SECONDARY, width=180), self.sup_temp_slider, self.sup_temp_label]),
                    ft.Row([self.tokens_input, self.retries_input], spacing=16),
                ], spacing=16),
                **card_style(),
            ),

            # Storage
            self._section_header("Lưu trữ"),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"Database: npb_podcast.db ({db_size_mb:.1f} MB)", size=13, color=TEXT_SECONDARY),
                    ft.Row([
                        ft.Text(f"Bài viết: {article_count}", size=13, color=TEXT_SECONDARY),
                        ft.Text(f"Logs: {log_count}", size=13, color=TEXT_SECONDARY),
                    ], spacing=24),
                    ft.Container(height=8),
                    ft.Row([
                        outlined_button("Xóa logs cũ (>30 ngày)", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=self._on_delete_logs),
                        outlined_button("Export DB", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self._on_export_db),
                    ], spacing=12),
                ], spacing=8),
                **card_style(),
            ),

            # Save button
            ft.Container(height=8),
            ft.Row([
                accent_button("LƯU CẤU HÌNH", icon=ft.Icons.SAVE_ROUNDED, on_click=self._on_save, width=200),
                self.save_msg,
            ], spacing=12),
            ft.Container(height=24),
        ]

    def _load_values(self):
        """Load all settings, decrypting API keys."""
        all_settings = get_all_settings()
        self.vals = {}
        for key, info in all_settings.items():
            if info["encrypted"]:
                self.vals[key] = decrypt(info["value"], self.machine_code)
            else:
                self.vals[key] = info["value"]

    def _section_header(self, text: str) -> ft.Text:
        return ft.Text(text, size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)

    def _key_row(self, text_field: ft.TextField) -> ft.Row:
        return ft.Row([text_field], spacing=8)

    def _model_dropdown(self, label: str, current: str) -> ft.Dropdown:
        return ft.Dropdown(
            label=label,
            value=current if current in GEMINI_MODELS else GEMINI_MODELS[0],
            options=[ft.dropdown.Option(m) for m in GEMINI_MODELS],
            bgcolor=BG_ELEVATED,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER,
            focused_border_color=ACCENT,
            border_radius=6,
        )

    def _on_slider(self, e, label: ft.Text):
        label.value = f"{e.control.value:.1f}"
        self._page.update()

    def _on_save(self, e):
        """Save all settings to SQLite."""
        mc = self.machine_code

        # Encrypt and save API keys
        for key, input_field in [
            (KEY_WRITER, self.key_writer_input),
            (KEY_EDITOR, self.key_editor_input),
            (KEY_ARCHITECT, self.key_architect_input),
        ]:
            val = input_field.value.strip()
            if val:
                set_setting(key, encrypt(val, mc), encrypted=True)

        # Save models
        set_setting(MODEL_DATA, self.model_data_dd.value)
        set_setting(MODEL_ANALYSIS, self.model_analysis_dd.value)
        set_setting(MODEL_WRITER, self.model_writer_dd.value)
        set_setting(MODEL_SUPERVISOR, self.model_supervisor_dd.value)

        # Save pipeline config
        set_setting(TEMPERATURE, f"{self.temp_slider.value:.1f}")
        set_setting(SUPERVISOR_TEMP, f"{self.sup_temp_slider.value:.1f}")
        set_setting(MAX_TOKENS, self.tokens_input.value.strip() or "16384")
        set_setting(MAX_RETRIES, self.retries_input.value.strip() or "2")

        self.save_msg.value = "Đã lưu!"
        self.save_msg.color = SUCCESS
        self._page.update()

    def _on_delete_logs(self, e):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            delete_old_logs(30)
            self._build()
            self._page.update()
            show_snackbar(self._page, "Đã xóa logs cũ", 2000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Xóa logs cũ?"),
            content=ft.Text("Xóa tất cả agent logs và pipeline runs cũ hơn 30 ngày."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Xóa"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _on_export_db(self, e):
        import shutil
        from db.database import get_db_path

        def on_result(e: ft.FilePickerResultEvent):
            if e.path:
                shutil.copy2(get_db_path(), e.path)
                show_snackbar(self._page, f"Đã export: {e.path}", 3000)

        picker = ft.FilePicker(on_result=on_result)
        self._page.overlay.append(picker)
        self._page.update()
        picker.save_file(
            file_name="npb_podcast_backup.db",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["db"],
        )
