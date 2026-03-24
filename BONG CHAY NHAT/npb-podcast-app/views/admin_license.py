"""
Admin License Tab — Manage licenses, extend expiry, revoke, suspend.
Requires admin login to license-manager backend.
"""

import flet as ft
from theme import (
    show_snackbar, show_dialog, close_dialog,
    BG_CARD, BG_ELEVATED, BORDER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT, SUCCESS, DANGER, WARNING, INFO,
    card_style, accent_button, danger_button, outlined_button, input_field, status_badge,
)
from services import admin_license_service as admin_svc

PER_PAGE = 15


class AdminLicenseTab(ft.Column):
    """Admin license management view."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=12)
        self._page = page
        self.current_page = 1
        self.total_pages = 1
        self.search_value = ""
        self.status_filter = ""
        self._licenses = []

        self._build_initial()

    def _build_initial(self):
        """Show login or license list based on auth state."""
        if admin_svc.is_logged_in():
            self._build_main()
        else:
            self._build_login()

    def _build_login(self):
        """Build admin login form."""
        self.email_input = input_field(label="Email", hint="admin@example.com", expand=True)
        self.password_input = input_field(label="Password", password=True, expand=True)
        self.login_msg = ft.Text("", size=12, color=DANGER)
        self.login_loading = ft.ProgressRing(width=18, height=18, stroke_width=2, color=ACCENT, visible=False)

        self.controls = [
            ft.Text("Quản lý License", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    ft.Text("Đăng nhập Admin", size=16, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Text("Dùng tài khoản admin trên License Server", size=12, color=TEXT_MUTED),
                    ft.Container(height=12),
                    self.email_input,
                    self.password_input,
                    ft.Container(height=8),
                    ft.Row([
                        accent_button("Đăng nhập", icon=ft.Icons.LOGIN_ROUNDED, on_click=self._on_login),
                        self.login_loading,
                    ], spacing=12),
                    self.login_msg,
                ], spacing=8),
                width=400,
                **card_style(),
            ),
        ]

    def _on_login(self, e):
        email = self.email_input.value.strip()
        password = self.password_input.value.strip()
        if not email or not password:
            self.login_msg.value = "Nhập email và password"
            self._page.update()
            return

        self.login_loading.visible = True
        self.login_msg.value = ""
        self._page.update()

        result = admin_svc.login(email, password)

        self.login_loading.visible = False
        if result["success"]:
            self._build_main()
            self._page.update()
        else:
            self.login_msg.value = result["message"]
            self._page.update()

    def _build_main(self):
        """Build the main license management view."""
        admin_email = admin_svc.get_admin_email()

        # Search and filters
        self.search_input = input_field(hint="Tìm license key, email...", expand=True, on_change=self._on_search)
        self.status_dd = ft.Dropdown(
            value="",
            options=[
                ft.dropdown.Option("", "Tất cả"),
                ft.dropdown.Option("ACTIVE", "Active"),
                ft.dropdown.Option("EXPIRED", "Expired"),
                ft.dropdown.Option("SUSPENDED", "Suspended"),
                ft.dropdown.Option("REVOKED", "Revoked"),
            ],
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY, label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER, focused_border_color=ACCENT, border_radius=6,
            width=140, on_select=self._on_filter,
        )

        # License list
        self.license_list = ft.Column(spacing=6, expand=True, scroll=ft.ScrollMode.AUTO)

        # Pagination
        self.page_label = ft.Text("1/1", size=12, color=TEXT_MUTED)
        self.prev_btn = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_size=18, icon_color=TEXT_SECONDARY, on_click=self._prev)
        self.next_btn = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_size=18, icon_color=TEXT_SECONDARY, on_click=self._next)
        self.total_text = ft.Text("", size=12, color=TEXT_MUTED)

        # Loading
        self.list_loading = ft.ProgressBar(visible=False, color=ACCENT, bgcolor=BORDER, height=3)

        self.controls = [
            ft.Row([
                ft.Text("Quản lý License", size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(f"Admin: {admin_email}", size=12, color=TEXT_MUTED),
                outlined_button("Đăng xuất", icon=ft.Icons.LOGOUT_ROUNDED, on_click=self._on_logout),
            ]),
            ft.Row([
                self.search_input,
                self.status_dd,
                ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color=TEXT_SECONDARY, tooltip="Refresh", on_click=lambda e: self._load_licenses()),
            ], spacing=8),
            self.list_loading,
            self.license_list,
            ft.Row([
                self.total_text,
                ft.Container(expand=True),
                self.prev_btn,
                self.page_label,
                self.next_btn,
            ]),
        ]

        self._load_licenses()

    def _load_licenses(self):
        """Load licenses from admin API."""
        self.list_loading.visible = True
        self._page.update()

        result = admin_svc.get_licenses(
            page=self.current_page,
            limit=PER_PAGE,
            status=self.status_filter,
            search=self.search_value,
        )

        self.list_loading.visible = False

        if not result["success"]:
            if result.get("auth_error"):
                admin_svc.logout()
                self._build_login()
                self._page.update()
                return
            show_snackbar(self._page, result["message"], 3000)
            self._page.update()
            return

        data = result.get("data", {})
        self._licenses = data.get("licenses", data.get("items", []))
        total = data.get("total", data.get("totalCount", len(self._licenses)))
        self.total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

        self.license_list.controls.clear()

        if not self._licenses:
            self.license_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.BADGE_OUTLINED, size=40, color=TEXT_MUTED),
                        ft.Text("Không có license nào", size=13, color=TEXT_MUTED),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.Alignment(0, 0),
                    padding=30,
                )
            )
        else:
            for lic in self._licenses:
                self.license_list.controls.append(self._license_card(lic))

        self.page_label.value = f"{self.current_page}/{self.total_pages}"
        self.total_text.value = f"Tổng: {total}"
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= self.total_pages
        self._page.update()

    def _license_card(self, lic: dict) -> ft.Container:
        """Build a card for one license."""
        lic_id = lic.get("id", "")
        key = lic.get("licenseKey", "???")
        status = lic.get("status", "UNKNOWN")
        expires = (lic.get("expiresAt") or "Không giới hạn")[:10]
        user_info = lic.get("user", {})
        email = user_info.get("email", "") if isinstance(user_info, dict) else ""
        product = lic.get("product", {})
        product_name = product.get("name", "") if isinstance(product, dict) else ""
        plan = lic.get("plan", {})
        plan_name = plan.get("name", "") if isinstance(plan, dict) else ""
        max_devices = lic.get("maxDevices", 1)
        active_devices = lic.get("_count", {}).get("deviceActivations", 0) if isinstance(lic.get("_count"), dict) else 0

        # Masked key
        masked = key[:8] + "••••" + key[-4:] if len(key) > 12 else key

        # Action menu
        actions_row = ft.Row([
            ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH_ROUNDED, icon_size=16, icon_color=SUCCESS,
                tooltip="Gia hạn", on_click=lambda e, lid=lic_id: self._show_extend(lid),
            ),
            ft.IconButton(
                icon=ft.Icons.PAUSE_CIRCLE_ROUNDED, icon_size=16, icon_color=WARNING,
                tooltip="Suspend", on_click=lambda e, lid=lic_id: self._do_suspend(lid),
            ),
            ft.IconButton(
                icon=ft.Icons.BLOCK_ROUNDED, icon_size=16, icon_color=DANGER,
                tooltip="Thu hồi", on_click=lambda e, lid=lic_id: self._do_revoke(lid),
            ),
            ft.IconButton(
                icon=ft.Icons.DEVICES_ROUNDED, icon_size=16, icon_color=INFO,
                tooltip="Reset devices", on_click=lambda e, lid=lic_id: self._do_reset(lid),
            ),
        ], spacing=0)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(masked, size=14, color=TEXT_PRIMARY, weight=ft.FontWeight.W_600,
                            selectable=True, expand=True),
                    status_badge(status),
                ], spacing=8),
                ft.Row([
                    ft.Text(email, size=12, color=TEXT_MUTED, expand=True) if email else ft.Container(),
                    ft.Text(f"{product_name} / {plan_name}", size=12, color=TEXT_SECONDARY) if product_name else ft.Container(),
                ], spacing=8),
                ft.Row([
                    ft.Text(f"Hết hạn: {expires}", size=11, color=TEXT_MUTED),
                    ft.Text(f"Devices: {active_devices}/{max_devices}", size=11, color=TEXT_MUTED),
                    ft.Container(expand=True),
                    actions_row,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=4),
            padding=12,
            bgcolor=BG_CARD,
            border=ft.border.all(1, BORDER),
            border_radius=8,
        )

    # === Actions ===

    def _show_extend(self, license_id: str):
        """Show extend dialog."""
        days_input = input_field(label="Số ngày gia hạn", value="30")

        def on_confirm(e):
            close_dialog(self._page, dialog)
            days = int(days_input.value.strip() or "30")
            result = admin_svc.extend_license(license_id, days)
            if result["success"]:
                show_snackbar(self._page, f"Đã gia hạn {days} ngày", 2000)
                self._load_licenses()
            else:
                show_snackbar(self._page, result["message"], 3000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Gia hạn License"),
            content=ft.Column([
                ft.Text(f"ID: {license_id[:12]}...", size=12, color=TEXT_MUTED),
                days_input,
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Gia hạn"), style=ft.ButtonStyle(color=SUCCESS), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _do_revoke(self, license_id: str):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            result = admin_svc.revoke_license(license_id, reason="Admin revoked from Flet app")
            if result["success"]:
                show_snackbar(self._page, "Đã thu hồi license", 2000)
                self._load_licenses()
            else:
                show_snackbar(self._page, result["message"], 3000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Thu hồi License?"),
            content=ft.Text("License sẽ bị vô hiệu hóa vĩnh viễn. Không thể hoàn tác."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Thu hồi"), style=ft.ButtonStyle(color=DANGER), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _do_suspend(self, license_id: str):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            result = admin_svc.suspend_license(license_id, reason="Admin suspended from Flet app")
            if result["success"]:
                show_snackbar(self._page, "Đã tạm ngưng license", 2000)
                self._load_licenses()
            else:
                show_snackbar(self._page, result["message"], 3000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Tạm ngưng License?"),
            content=ft.Text("License sẽ bị suspend. Có thể kích hoạt lại sau."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Suspend"), style=ft.ButtonStyle(color=WARNING), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    def _do_reset(self, license_id: str):
        def on_confirm(e):
            close_dialog(self._page, dialog)
            result = admin_svc.reset_devices(license_id, reason="Admin reset from Flet app")
            if result["success"]:
                show_snackbar(self._page, "Đã reset tất cả thiết bị", 2000)
                self._load_licenses()
            else:
                show_snackbar(self._page, result["message"], 3000)

        def on_cancel(e):
            close_dialog(self._page, dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Reset Devices?"),
            content=ft.Text("Tất cả thiết bị đang kích hoạt sẽ bị hủy. User cần activate lại."),
            actions=[
                ft.TextButton(content=ft.Text("Hủy"), on_click=on_cancel),
                ft.TextButton(content=ft.Text("Reset"), style=ft.ButtonStyle(color=WARNING), on_click=on_confirm),
            ],
        )
        show_dialog(self._page, dialog)

    # === Navigation ===

    def _on_search(self, e):
        self.search_value = e.control.value
        self.current_page = 1
        self._load_licenses()

    def _on_filter(self, e):
        self.status_filter = self.status_dd.value or ""
        self.current_page = 1
        self._load_licenses()

    def _prev(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self._load_licenses()

    def _next(self, e):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._load_licenses()

    def _on_logout(self, e):
        admin_svc.logout()
        self._build_login()
        self._page.update()

    def refresh(self):
        """Refresh when switching to this tab."""
        if admin_svc.is_logged_in():
            self._load_licenses()
