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

        # Run in background thread to avoid UI freeze
        import threading

        def _do_activate():
            result = license_service.activate(key)

            def _update_ui():
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

            self._page.run_thread(_update_ui)

        threading.Thread(target=_do_activate, daemon=True).start()

    def _copy_machine_code(self, e):
        self._page.run_task(ft.Clipboard().set, self.hw_info["machine_code"])
        show_snackbar(self._page, "Đã copy Machine Code", 2000)


class LicenseTab(ft.Column):
    """License management tab — status, countdown, version, device info."""

    _DEBOUNCE_SECONDS = 300  # 5 minutes

    def __init__(self, page: ft.Page, on_deactivated=None, on_update_available=None):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.on_deactivated = on_deactivated
        self.on_update_available = on_update_available
        self._last_refresh_ts = 0
        self._show_full_key = False
        self._cached_update = None
        self._build()

    def refresh(self):
        """Called when tab becomes visible. Debounce to avoid API spam."""
        import time
        now = time.time()
        if now - self._last_refresh_ts > self._DEBOUNCE_SECONDS:
            self._last_refresh_ts = now
            self._build()
            self._page.update()

    def _build(self):
        info = license_service.get_license_info()
        hw = machine_id.get_hardware_info()

        if not info:
            self.controls = [ft.Text("Chưa kích hoạt license", color=TEXT_MUTED)]
            return

        days_info = license_service.get_days_remaining()

        # === SECTION 1: License Status ===
        license_section = self._build_license_section(info, days_info)

        # === SECTION 2: Version & Update ===
        version_section = self._build_version_section()

        # === SECTION 3: Device Info ===
        device_section = self._build_device_section(hw)

        self.controls = [
            ft.Text("Quản lý License", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            license_section,
            version_section,
            device_section,
        ]

    # ── Section Builders ──────────────────────────────────────

    def _build_license_section(self, info: dict, days_info: dict) -> ft.Container:
        """Section 1: License status with countdown."""
        key = info["license_key"]
        masked_key = key[:4] + "-" + "····-····-" + key[-4:] if len(key) > 8 else key
        display_key = key if self._show_full_key else masked_key
        status = info["status"]

        # Countdown
        days = days_info["days"]
        expired = days_info["expired"]

        if expired:
            countdown_text = f"HẾT HẠN {abs(days)} NGÀY TRƯỚC"
            countdown_color = DANGER
            countdown_icon = ft.Icons.ERROR_ROUNDED
        elif days <= 7:
            countdown_text = f"CÒN {days} NGÀY"
            countdown_color = DANGER
            countdown_icon = ft.Icons.WARNING_ROUNDED
        elif days <= 30:
            countdown_text = f"CÒN {days} NGÀY"
            countdown_color = WARNING
            countdown_icon = ft.Icons.ACCESS_TIME_ROUNDED
        else:
            countdown_text = f"CÒN {days} NGÀY"
            countdown_color = SUCCESS
            countdown_icon = ft.Icons.CHECK_CIRCLE_ROUNDED

        # Progress bar value (0.0 - 1.0)
        if not expired and days_info["total_estimate"] > 0:
            progress_val = max(0.0, min(1.0, days / days_info["total_estimate"]))
        else:
            progress_val = 0.0

        # Override status display if expired
        display_status = "expired" if expired else status

        # Verify message control
        self.verify_msg = ft.Text("", size=12, color=TEXT_MUTED)

        return ft.Container(
            content=ft.Column([
                # Header row: status badge + plan
                ft.Row([
                    status_badge(display_status),
                    ft.Text(info.get("plan", ""), size=14, color=TEXT_SECONDARY, weight=ft.FontWeight.W_500),
                ], spacing=12),
                ft.Container(height=8),

                # Countdown highlight box
                ft.Container(
                    content=ft.Row([
                        ft.Icon(countdown_icon, color=countdown_color, size=28),
                        ft.Text(countdown_text, size=22, weight=ft.FontWeight.BOLD, color=countdown_color),
                    ], spacing=12, alignment=ft.MainAxisAlignment.CENTER),
                    bgcolor="#0A0A0B",
                    border=ft.border.all(1, countdown_color),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Container(height=4),

                # Progress bar
                ft.Row([
                    ft.ProgressBar(
                        value=progress_val,
                        color=countdown_color,
                        bgcolor=BORDER,
                        expand=True,
                    ),
                    ft.Text(
                        f"{days}/{days_info['total_estimate']}" if not expired else "0",
                        size=11, color=TEXT_MUTED,
                    ),
                ], spacing=8),
                ft.Container(height=8),

                # Info rows
                ft.Row([
                    ft.Text("License Key:", size=13, color=TEXT_MUTED, width=120),
                    ft.Text(display_key, size=13, color=TEXT_PRIMARY, selectable=True, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.VISIBILITY_ROUNDED if not self._show_full_key else ft.Icons.VISIBILITY_OFF_ROUNDED,
                        icon_size=16, icon_color=TEXT_MUTED, tooltip="Hiện/ẩn key",
                        on_click=self._toggle_key_visibility,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.COPY_ROUNDED, icon_size=16, icon_color=TEXT_MUTED,
                        tooltip="Copy key",
                        on_click=lambda e: self._copy_text(key),
                    ),
                ]),
                self._info_row("Sản phẩm", info.get("product", "")),
                self._info_row("Hết hạn", self._format_expiry(days_info["expires_at"])),
                self._info_row("Xác minh lần cuối", self._format_verified(info.get("verified_at", ""))),
                ft.Container(height=8),

                # Action buttons
                ft.Row([
                    outlined_button("Verify ngay", icon=ft.Icons.REFRESH_ROUNDED, on_click=self._on_verify),
                    danger_button("Hủy kích hoạt", icon=ft.Icons.LOCK_OPEN_ROUNDED, on_click=self._on_deactivate),
                ], spacing=12),
                self.verify_msg,
            ], spacing=6),
            **card_style(),
        )

    def _build_version_section(self) -> ft.Container:
        """Section 2: Version & update management."""
        current = get_current_version()

        self.update_status = ft.Text("Nhấn kiểm tra để xem phiên bản mới.", size=12, color=TEXT_MUTED)
        self.update_changelog = ft.Column([], spacing=4)
        self.update_btn = outlined_button(
            "Kiểm tra cập nhật", icon=ft.Icons.SYSTEM_UPDATE_ROUNDED, on_click=self._on_check_update,
        )
        self.install_btn = accent_button(
            "Tải & Cài đặt", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self._on_install_update,
        )
        self.install_btn.visible = False

        return ft.Container(
            content=ft.Column([
                ft.Text("Phiên bản & Cập nhật", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                ft.Container(height=4),
                self._info_row("Version hiện tại", current),
                ft.Container(height=4),
                self.update_status,
                self.update_changelog,
                ft.Container(height=8),
                ft.Row([self.update_btn, self.install_btn], spacing=12),
            ], spacing=6),
            **card_style(),
        )

    def _build_device_section(self, hw: dict) -> ft.Container:
        """Section 3: Device info."""
        mc = hw["machine_code"]
        mc_short = mc[:16] + "..." + mc[-8:]

        return ft.Container(
            content=ft.Column([
                ft.Text("Thông tin thiết bị", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                ft.Container(height=4),
                self._info_row("CPU", hw["cpu"]),
                self._info_row("Mainboard", hw["mainboard"]),
                ft.Row([
                    ft.Text("Machine Code:", size=13, color=TEXT_MUTED, width=120),
                    ft.Text(mc_short, size=13, color=TEXT_PRIMARY, selectable=True, expand=True),
                    ft.IconButton(
                        icon=ft.Icons.COPY_ROUNDED, icon_size=16, icon_color=TEXT_MUTED,
                        tooltip="Copy Machine Code",
                        on_click=lambda e: self._copy_text(mc),
                    ),
                ]),
            ], spacing=6),
            **card_style(),
        )

    # ── Helpers ───────────────────────────────────────────────

    def _info_row(self, label: str, value: str) -> ft.Row:
        return ft.Row([
            ft.Text(f"{label}:", size=13, color=TEXT_MUTED, width=120),
            ft.Text(value, size=13, color=TEXT_PRIMARY, selectable=True),
        ])

    def _format_verified(self, iso_str: str) -> str:
        if not iso_str:
            return "Chưa xác minh"
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

    def _format_expiry(self, expires_str: str) -> str:
        if not expires_str:
            return "N/A"
        try:
            if "T" in expires_str:
                from datetime import datetime
                dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M")
            return expires_str
        except Exception:
            return expires_str

    def _copy_text(self, text: str):
        self._page.run_task(ft.Clipboard().set, text)
        show_snackbar(self._page, "Đã copy!", 1500)

    def _toggle_key_visibility(self, e):
        self._show_full_key = not self._show_full_key
        self._build()
        self._page.update()

    # ── Actions ───────────────────────────────────────────────

    def _on_verify(self, e):
        self.verify_msg.value = "Đang xác minh..."
        self.verify_msg.color = TEXT_MUTED
        self._page.update()

        import threading

        def _do_verify():
            result = license_service.verify()

            def _update():
                self.verify_msg.value = result["message"]
                self.verify_msg.color = SUCCESS if result["valid"] else DANGER
                self._page.update()
                # Rebuild to refresh verified_at & countdown
                self._build()
                self._page.update()

            self._page.run_thread(_update)

        threading.Thread(target=_do_verify, daemon=True).start()

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
            content=ft.Text("Bạn sẽ cần nhập lại license key để sử dụng app trên máy này."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Xác nhận hủy"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _on_check_update(self, e):
        self.update_status.value = "Đang kiểm tra..."
        self.update_status.color = TEXT_MUTED
        self.update_btn.disabled = True
        self._page.update()

        import threading

        def _do_check():
            update = check_for_update()

            def _update_ui():
                self.update_btn.disabled = False
                if update:
                    self._cached_update = update
                    self.update_status.value = f"Có bản mới: v{update['version']}"
                    self.update_status.color = ACCENT

                    # Show changelog
                    changelog = update.get("changelog", "")
                    self.update_changelog.controls.clear()
                    if changelog:
                        self.update_changelog.controls.append(
                            ft.Container(
                                content=ft.Text(changelog, size=12, color=TEXT_SECONDARY),
                                bgcolor=BG_ELEVATED,
                                border_radius=6,
                                padding=10,
                            )
                        )

                    self.install_btn.visible = True

                    # Notify layout for badge
                    if self.on_update_available:
                        self.on_update_available(True)
                else:
                    self._cached_update = None
                    self.update_status.value = "Bạn đang dùng phiên bản mới nhất."
                    self.update_status.color = SUCCESS
                    self.update_changelog.controls.clear()
                    self.install_btn.visible = False
                self._page.update()

            self._page.run_thread(_update_ui)

        threading.Thread(target=_do_check, daemon=True).start()

    def _on_install_update(self, e):
        if not self._cached_update:
            return

        def on_update(e):
            close_dialog(self._page, dialog)
            download_and_install(self._cached_update["download_url"])
            self._page.window.close()

        def on_skip(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text(f"Cập nhật lên v{self._cached_update['version']}?"),
            content=ft.Text("App sẽ đóng và mở bản cài đặt mới."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_skip),
                ft.TextButton(content=ft.Text("Cập nhật ngay"), style=ft.ButtonStyle(color=ACCENT), on_click=on_update),
            ],
        )
        show_dialog(self._page, dialog)
