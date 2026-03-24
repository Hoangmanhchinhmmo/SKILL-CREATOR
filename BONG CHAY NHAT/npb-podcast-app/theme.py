"""
NPB Podcast Writer — Theme & Color Tokens
Dark SaaS style, accent orange #F97316
"""

import flet as ft

# === Color Tokens ===
BG_PRIMARY = "#0A0A0B"
BG_CARD = "#141416"
BG_ELEVATED = "#1C1C1F"
BORDER = "#27272A"
BORDER_HOVER = "#3F3F46"
TEXT_PRIMARY = "#FAFAFA"
TEXT_SECONDARY = "#A1A1AA"
TEXT_MUTED = "#71717A"
ACCENT = "#F97316"
ACCENT_HOVER = "#EA580C"
SUCCESS = "#22C55E"
WARNING = "#EAB308"
DANGER = "#EF4444"
INFO = "#3B82F6"

# === Dimensions ===
SIDEBAR_WIDTH = 60
SIDEBAR_EXPANDED = 200
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600
CARD_BORDER_RADIUS = 8
BUTTON_BORDER_RADIUS = 6

# === Font ===
FONT_FAMILY = "Inter"
FONT_MONO = "Consolas"


def get_theme() -> ft.Theme:
    """Return Flet Theme configured for Dark SaaS."""
    return ft.Theme(
        color_scheme_seed=ACCENT,
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            on_primary="#FFFFFF",
            surface=BG_PRIMARY,
            on_surface=TEXT_PRIMARY,
            error=DANGER,
            on_error="#FFFFFF",
            surface_container=BG_CARD,
            surface_container_high=BG_ELEVATED,
            outline=BORDER,
            outline_variant=BORDER_HOVER,
        ),
        text_theme=ft.TextTheme(
            body_medium=ft.TextStyle(color=TEXT_PRIMARY),
            body_small=ft.TextStyle(color=TEXT_SECONDARY),
            label_large=ft.TextStyle(color=TEXT_PRIMARY),
        ),
    )


def card_style() -> dict:
    """Common card container style."""
    return dict(
        bgcolor=BG_CARD,
        border_radius=CARD_BORDER_RADIUS,
        border=ft.border.all(1, BORDER),
        padding=16,
    )


def elevated_style() -> dict:
    """Elevated container style (sidebar, headers)."""
    return dict(
        bgcolor=BG_ELEVATED,
        border_radius=CARD_BORDER_RADIUS,
        border=ft.border.all(1, BORDER),
        padding=12,
    )


def accent_button(text: str, icon: str = None, on_click=None, width: int = None) -> ft.ElevatedButton:
    """Orange accent button."""
    return ft.ElevatedButton(
        content=ft.Text(text, color="#FFFFFF"),
        icon=icon,
        bgcolor=ACCENT,
        color="#FFFFFF",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BUTTON_BORDER_RADIUS),
        ),
        on_click=on_click,
        width=width,
    )


def danger_button(text: str, icon: str = None, on_click=None) -> ft.ElevatedButton:
    """Red danger button."""
    return ft.ElevatedButton(
        content=ft.Text(text, color="#FFFFFF"),
        icon=icon,
        bgcolor=DANGER,
        color="#FFFFFF",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=BUTTON_BORDER_RADIUS),
        ),
        on_click=on_click,
    )


def outlined_button(text: str, icon: str = None, on_click=None) -> ft.OutlinedButton:
    """Outlined button with border."""
    return ft.OutlinedButton(
        content=ft.Text(text, color=TEXT_SECONDARY),
        icon=icon,
        style=ft.ButtonStyle(
            color=TEXT_SECONDARY,
            side=ft.BorderSide(1, BORDER),
            shape=ft.RoundedRectangleBorder(radius=BUTTON_BORDER_RADIUS),
        ),
        on_click=on_click,
    )


def input_field(label: str = "", hint: str = "", password: bool = False,
                value: str = "", on_change=None, expand: bool = False) -> ft.TextField:
    """Styled text input field."""
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        password=password,
        can_reveal_password=password,
        bgcolor=BG_ELEVATED,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        hint_style=ft.TextStyle(color=TEXT_MUTED),
        border_color=BORDER,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        border_radius=BUTTON_BORDER_RADIUS,
        on_change=on_change,
        expand=expand,
    )


def show_snackbar(page: ft.Page, message: str, duration: int = 2000, bgcolor: str = None):
    """Show a snackbar message (Flet 0.82 compatible)."""
    sb = ft.SnackBar(content=ft.Text(message), duration=duration)
    if bgcolor:
        sb.bgcolor = bgcolor
    page.overlay.append(sb)
    sb.open = True
    page.update()


def show_dialog(page: ft.Page, dialog: ft.AlertDialog):
    """Show an AlertDialog (Flet 0.82 compatible)."""
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def close_dialog(page: ft.Page, dialog: ft.AlertDialog):
    """Close an AlertDialog."""
    dialog.open = False
    page.update()


def status_badge(status: str) -> ft.Container:
    """Colored status badge."""
    color_map = {
        "active": SUCCESS,
        "completed": SUCCESS,
        "passed": SUCCESS,
        "running": INFO,
        "in_progress": INFO,
        "retrying": WARNING,
        "warning": WARNING,
        "grace": WARNING,
        "failed": DANGER,
        "expired": DANGER,
        "revoked": DANGER,
        "waiting": TEXT_MUTED,
        "pending": TEXT_MUTED,
    }
    color = color_map.get(status.lower(), TEXT_MUTED)

    return ft.Container(
        content=ft.Text(status.upper(), size=11, color="#FFFFFF", weight=ft.FontWeight.BOLD),
        bgcolor=color,
        border_radius=4,
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
    )
