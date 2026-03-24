"""
License Tab + First-Launch Screen.
"""

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, WARNING,
    card_style, accent_button, danger_button, outlined_button, input_field, status_badge,
)
from services import license_service, machine_id
from services.updater import check_for_update, download_and_install, get_current_version


class FirstLaunchView(ft.Column):
    """Full-screen activation view shown when no license exists."""

    def __init__(self, page: ft.Page, on_activated=None):
        super().__init__(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        )
        self._page = page
        self.on_activated = on_activated
        self.hw_info = machine_id.get_hardware_info()

        # Controls
        self.key_input = input_field(
            label="License Key",
            hint="NPB-XXXX-XXXX-XXXX",
            expand=True,
        )
        self.message_text = ft.Text("", size=13, color=DANGER)
        self.loading = ft.ProgressRing(width=20, height=20, stroke_width=2, color=ACCENT, visible=False)

        self.activate_btn = accent_button(
            "KÍCH HOẠT", icon=ft.Icons.VERIFIED_ROUNDED, on_click=self._on_activate, width=200,
        )

        machine_code_short = self.hw_info["machine_code"][:12] + "..." + self.hw_info["machine_code"][-6:]

        self.controls = [
            ft.Container(height=40),
            # Logo
            ft.Icon(ft.Icons.PODCASTS_ROUNDED, size=64, color=ACCENT),
            ft.Text("NPB Podcast Writer", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Text("Multi-Agent Podcast Script Generator", size=14, color=TEXT_SECONDARY),
            ft.Container(height=20),
            # Activation card
            ft.Container(
                content=ft.Column([
                    ft.Text("Nhập License Key để kích hoạt:", size=14, color=TEXT_SECONDARY),
                    ft.Container(height=8),
                    self.key_input,
                    ft.Container(height=4),
                    ft.Row([
                        ft.Text(f"Machine Code: {machine_code_short}", size=12, color=TEXT_MUTED),
                        ft.IconButton(
                            icon=ft.Icons.COPY_ROUNDED, icon_size=16, icon_color=TEXT_MUTED,
                            tooltip="Copy Machine Code",
                            on_click=self._copy_machine_code,
                        ),
                    ]),
                    ft.Container(height=12),
                    ft.Row(
                        [self.activate_btn, self.loading],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    self.message_text,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                width=450,
                **card_style(),
            ),
            ft.Container(height=16),
            ft.TextButton(
                content=ft.Text("Chưa có license? Mua tại đây"),
                style=ft.ButtonStyle(color=ACCENT),
            ),
        ]

    def _on_activate(self, e):
        key = self.key_input.value.strip()
        if not key:
            self.message_text.value = "Vui lòng nhập License Key"
            self.message_text.color = DANGER
            self._page.update()
            return

        self.loading.visible = True
        self.activate_btn.disabled = True
        self.message_text.value = "Đang kích hoạt..."
        self.message_text.color = TEXT_MUTED
        self._page.update()

        result = license_service.activate(key)

        self.loading.visible = False
        self.activate_btn.disabled = False

        if result["success"]:
            self.message_text.value = result["message"]
            self.message_text.color = SUCCESS
            self._page.update()
            if self.on_activated:
                self.on_activated()
        else:
            self.message_text.value = result["message"]
            self.message_text.color = DANGER
            self._page.update()

    def _copy_machine_code(self, e):
        self._page.set_clipboard(self.hw_info["machine_code"])
        show_snackbar(self._page, "Đã copy Machine Code", 2000)


class LicenseTab(ft.Column):
    """License info + management tab."""

    def __init__(self, page: ft.Page, on_deactivated=None):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.on_deactivated = on_deactivated
        self._build()

    def _build(self):
        info = license_service.get_license_info()
        hw = machine_id.get_hardware_info()

        if not info:
            self.controls = [ft.Text("Chưa kích hoạt license", color=TEXT_MUTED)]
            return

        # Mask license key
        key = info["license_key"]
        masked_key = key[:4] + "-" + "••••-••••-" + key[-4:] if len(key) > 8 else key

        # Status color
        status = info["status"]

        # Verify message
        self.verify_msg = ft.Text("", size=12, color=TEXT_MUTED)

        self.controls = [
            ft.Text("License", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            # Status card
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        status_badge(status),
                        ft.Text(info.get("plan", ""), size=14, color=TEXT_SECONDARY),
                    ], spacing=12),
                    ft.Container(height=12),
                    self._info_row("License Key", masked_key),
                    self._info_row("Product", info.get("product", "")),
                    self._info_row("Hết hạn", info.get("expires_at", "N/A")),
                    self._info_row("Verify lần cuối", self._format_verified(info.get("verified_at", ""))),
                ], spacing=8),
                **card_style(),
            ),
            # Device info
            ft.Text("Thiết bị", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            ft.Container(
                content=ft.Column([
                    self._info_row("Machine Code", hw["machine_code"][:20] + "..."),
                    self._info_row("CPU", hw["cpu"]),
                    self._info_row("Mainboard", hw["mainboard"]),
                ], spacing=8),
                **card_style(),
            ),
            # Actions
            ft.Text("Hành động", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            ft.Row([
                outlined_button("Verify ngay", icon=ft.Icons.REFRESH_ROUNDED, on_click=self._on_verify),
                danger_button("Hủy kích hoạt thiết bị này", icon=ft.Icons.LOCK_OPEN_ROUNDED, on_click=self._on_deactivate),
            ], spacing=12),
            self.verify_msg,
            # App info
            ft.Container(height=12),
            ft.Text("Thông tin app", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            ft.Container(
                content=ft.Column([
                    self._info_row("Version", get_current_version()),
                    ft.Container(height=8),
                    outlined_button("Kiểm tra update", icon=ft.Icons.SYSTEM_UPDATE_ROUNDED, on_click=self._on_check_update),
                ], spacing=8),
                **card_style(),
            ),
        ]

    def _info_row(self, label: str, value: str) -> ft.Row:
        return ft.Row([
            ft.Text(f"{label}:", size=13, color=TEXT_MUTED, width=140),
            ft.Text(value, size=13, color=TEXT_PRIMARY, selectable=True),
        ])

    def _format_verified(self, iso_str: str) -> str:
        if not iso_str:
            return "Chưa verify"
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso_str)
            elapsed = (datetime.now() - dt).total_seconds()
            if elapsed < 3600:
                return f"{int(elapsed / 60)} phút trước"
            elif elapsed < 86400:
                return f"{int(elapsed / 3600)} giờ trước"
            else:
                return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_str

    def _on_verify(self, e):
        self.verify_msg.value = "Đang verify..."
        self.verify_msg.color = TEXT_MUTED
        self._page.update()

        result = license_service.verify()
        self.verify_msg.value = result["message"]
        self.verify_msg.color = SUCCESS if result["valid"] else DANGER
        self._page.update()

        # Rebuild to update verified_at
        self._build()
        self._page.update()

    def _on_deactivate(self, e):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            license_service.deactivate()
            if self.on_deactivated:
                self.on_deactivated()

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Hủy kích hoạt?"),
            content=ft.Text("Bạn sẽ cần nhập lại license key để sử dụng app."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Xác nhận hủy"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _on_check_update(self, e):
        update = check_for_update()
        if update:
            def on_update(e):
                close_dialog(self._page, dialog)
                download_and_install(update["download_url"])
                self._page.window.close()

            def on_skip(e):
                close_dialog(self._page, dialog)

            dialog = ft.AlertDialog(
                title=ft.Text(f"Có bản mới v{update['version']}"),
                content=ft.Text(update.get("changelog", "")),
                actions=[
                    ft.TextButton(content=ft.Text("Bỏ qua"), on_click=on_skip),
                    ft.TextButton(content=ft.Text("Cập nhật"), style=ft.ButtonStyle(color=ACCENT), on_click=on_update),
                ],
            )
            show_dialog(self._page, dialog)
        else:
            show_snackbar(self._page, "Bạn đang dùng phiên bản mới nhất", 2000)
