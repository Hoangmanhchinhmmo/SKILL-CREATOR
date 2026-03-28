"""
Tab Config — Translation configuration: genre, audience, setting, keigo, narrator, style, models.
Supports 9Router: auto-fetch model list from 9Router API if configured.
"""

import flet as ft
import threading
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT, INFO, SUCCESS, DANGER,
    card_style, accent_button, outlined_button, input_field, show_snackbar,
    CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)
from db.models import get_setting, set_setting


GEMINI_MODELS_FALLBACK = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"]


def _get_available_models() -> tuple[list[str], str]:
    """Get available models. Try 9Router first, fallback to hardcoded Gemini.
    Returns (models_list, source_label).
    """
    router_url = get_setting("router_url")
    if not router_url:
        return GEMINI_MODELS_FALLBACK, "Gemini (mặc định)"

    # Import fetch function from settings
    from views.settings import _fetch_router_models
    router_api_key = get_setting("router_api_key")
    if router_api_key:
        from services.machine_id import get_machine_code
        from services.crypto import decrypt
        decrypted = decrypt(router_api_key, get_machine_code())
        router_api_key = decrypted or ""

    models = _fetch_router_models(router_url, router_api_key or "")
    if models:
        return models, f"9Router ({len(models)} models)"
    return GEMINI_MODELS_FALLBACK, "Gemini (9Router offline)"

GENRE_OPTIONS = ["Hành động", "Tình cảm", "Kinh dị", "Fantasy", "Đời thường", "Khoa học viễn tưởng", "Hài hước", "Khác"]
AUDIENCE_OPTIONS = ["Người lớn", "Thanh thiếu niên", "Trẻ em", "Tất cả"]
SETTING_OPTIONS = ["Hiện đại", "Cổ đại", "Fantasy", "Tương lai", "Khác"]

KEIGO_OPTIONS = [
    ("casual", "Casual — だ/である体"),
    ("polite", "Polite — です/ます体"),
    ("formal", "Formal — 敬語"),
]

NARRATOR_OPTIONS = [
    ("male", "Nam — 僕/俺"),
    ("female", "Nữ — 私/あたし"),
    ("neutral", "Trung tính — 私"),
]

STYLE_OPTIONS = [
    ("podcast", "Podcast script (có ngắt nghỉ, TTS)"),
    ("story", "Truyện thuần túy"),
    ("light_novel", "Light novel style"),
]

# DB keys for translator model defaults
DB_KEY_MODEL_ANALYZER = "translator_model_analyzer"
DB_KEY_MODEL_TRANSLATOR = "translator_model_translator"
DB_KEY_MODEL_REVIEWER = "translator_model_reviewer"
DB_KEY_CHANNEL_NAME = "translator_channel_name"
DB_KEY_FAST_MODE = "translator_fast_mode"

# Defaults
DEFAULT_MODEL_ANALYZER = "gemini-2.5-flash"
DEFAULT_MODEL_TRANSLATOR = "gemini-2.5-pro"
DEFAULT_MODEL_REVIEWER = "gemini-2.5-flash"
DEFAULT_CHANNEL = "にほんのチカラ・【海外の反応】"


def _load_saved(key: str, default: str) -> str:
    """Load saved setting from DB, or return default."""
    val = get_setting(key)
    return val if val else default


class TabConfig(ft.Column):
    """Config sub-tab — translation settings."""

    def __init__(self, page: ft.Page, state, on_next=None, on_back=None):
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self._state = state
        self._on_next = on_next
        self._on_back = on_back

        # Load saved defaults from DB
        saved_analyzer = _load_saved(DB_KEY_MODEL_ANALYZER, DEFAULT_MODEL_ANALYZER)
        saved_translator = _load_saved(DB_KEY_MODEL_TRANSLATOR, DEFAULT_MODEL_TRANSLATOR)
        saved_reviewer = _load_saved(DB_KEY_MODEL_REVIEWER, DEFAULT_MODEL_REVIEWER)
        saved_channel = _load_saved(DB_KEY_CHANNEL_NAME, DEFAULT_CHANNEL)
        saved_fast = _load_saved(DB_KEY_FAST_MODE, "false") == "true"

        # Load available models (9Router or fallback)
        self._available_models, self._model_source = _get_available_models()

        # ── Section 1: Phân tích truyện ──
        self._genre_dd = self._dropdown("Thể loại", GENRE_OPTIONS, state.config.get("genre", "Đời thường"))
        self._audience_dd = self._dropdown("Đối tượng", AUDIENCE_OPTIONS, state.config.get("audience", "Người lớn"))
        self._setting_dd = self._dropdown("Bối cảnh", SETTING_OPTIONS, state.config.get("setting", "Hiện đại"))

        # ── Section 2: Phong cách Nhật hóa ──
        self._keigo_dd = self._radio_group("keigo", KEIGO_OPTIONS, state.config.get("keigo", "casual"))
        self._narrator_dd = self._radio_group("narrator", NARRATOR_OPTIONS, state.config.get("narrator", "neutral"))
        self._style_dd = self._radio_group("style", STYLE_OPTIONS, state.config.get("style", "podcast"))

        # ── Section 3: Model settings ──
        # Ensure saved values exist in available models, otherwise use default
        if saved_analyzer not in self._available_models:
            saved_analyzer = self._available_models[0] if self._available_models else DEFAULT_MODEL_ANALYZER
        if saved_translator not in self._available_models:
            saved_translator = self._available_models[0] if self._available_models else DEFAULT_MODEL_TRANSLATOR
        if saved_reviewer not in self._available_models:
            saved_reviewer = self._available_models[0] if self._available_models else DEFAULT_MODEL_REVIEWER

        self._model_analyzer_dd = self._dropdown("Analyzer", self._available_models, saved_analyzer, width=220)
        self._model_translator_dd = self._dropdown("Translator", self._available_models, saved_translator, width=220)
        self._model_reviewer_dd = self._dropdown("Reviewer", self._available_models, saved_reviewer, width=220)
        self._model_source_text = ft.Text(self._model_source, size=11, color=SUCCESS if "9Router" in self._model_source else TEXT_MUTED)

        # ── Section 4: Tùy chọn nâng cao ──
        SPEED_OPTIONS = [
            ("safe", "Tuần tự — 1 đoạn/lần, giọng kể liền mạch nhất"),
            ("balanced", "Cân bằng — 3 đoạn/lần (khuyến nghị)"),
            ("fast", "Nhanh — 5 đoạn/lần"),
            ("turbo", "Turbo — 10 đoạn/lần, nhanh nhất"),
        ]
        saved_speed = "balanced" if saved_fast else "safe"
        self._speed_mode = self._radio_group("speed", SPEED_OPTIONS, saved_speed)
        self._channel_field = input_field(
            label="Tên kênh CTA",
            value=saved_channel,
            expand=True,
        )
        self._save_default_btn = ft.TextButton(
            content=ft.Text("Lưu mặc định", size=12, color=ACCENT),
            on_click=self._on_save_defaults,
        )

        # ── Advanced collapsed ──
        self._advanced_visible = False

        self._build_controls()

    def _dropdown(self, label: str, options: list[str], value: str, width: int = 250) -> ft.Dropdown:
        return ft.Dropdown(
            label=label,
            value=value,
            options=[ft.dropdown.Option(o) for o in options],
            bgcolor=BG_ELEVATED,
            color=TEXT_PRIMARY,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            border_color=BORDER,
            focused_border_color=ACCENT,
            border_radius=BUTTON_BORDER_RADIUS,
            width=width,
        )

    def _radio_group(self, key: str, options: list[tuple[str, str]], value: str) -> ft.RadioGroup:
        radios = []
        for val, label in options:
            radios.append(
                ft.Radio(
                    value=val,
                    label=label,
                    fill_color=ACCENT,
                    label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
                )
            )
        return ft.RadioGroup(
            value=value,
            content=ft.Column(radios, spacing=4),
        )

    def _build_controls(self):
        # Section 1
        section1 = ft.Container(
            content=ft.Column([
                ft.Text("📖 Phân tích truyện", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=BORDER),
                ft.Row([self._genre_dd, self._audience_dd, self._setting_dd],
                       spacing=16, wrap=True),
            ], spacing=12),
            **card_style(),
        )

        # Section 2
        section2 = ft.Container(
            content=ft.Column([
                ft.Text("🇯🇵 Phong cách Nhật hóa", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1, color=BORDER),
                ft.Row([
                    ft.Column([
                        ft.Text("Kính ngữ", size=13, color=TEXT_SECONDARY),
                        self._keigo_dd,
                    ], spacing=4),
                    ft.Column([
                        ft.Text("Giọng kể", size=13, color=TEXT_SECONDARY),
                        self._narrator_dd,
                    ], spacing=4),
                    ft.Column([
                        ft.Text("Style output", size=13, color=TEXT_SECONDARY),
                        self._style_dd,
                    ], spacing=4),
                ], spacing=32, wrap=True),
            ], spacing=12),
            **card_style(),
        )

        # Section 3: Models
        section3 = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("🤖 Model Pipeline", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Container(width=8),
                    self._model_source_text,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=16,
                        icon_color=TEXT_MUTED,
                        tooltip="Refresh danh sách models từ 9Router",
                        on_click=self._on_refresh_models,
                    ),
                    ft.Container(expand=True),
                    self._save_default_btn,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=BORDER),
                ft.Row([
                    ft.Column([
                        ft.Text("Analyzer", size=12, color=TEXT_MUTED),
                        ft.Text("Phân tích & tạo mapping", size=11, color=TEXT_MUTED, italic=True),
                        self._model_analyzer_dd,
                    ], spacing=2),
                    ft.Column([
                        ft.Text("Translator", size=12, color=TEXT_MUTED),
                        ft.Text("Chuyển đổi nội dung", size=11, color=TEXT_MUTED, italic=True),
                        self._model_translator_dd,
                    ], spacing=2),
                    ft.Column([
                        ft.Text("Reviewer", size=12, color=TEXT_MUTED),
                        ft.Text("Kiểm tra chất lượng", size=11, color=TEXT_MUTED, italic=True),
                        self._model_reviewer_dd,
                    ], spacing=2),
                ], spacing=16, wrap=True),
            ], spacing=8),
            **card_style(),
        )

        # Section 4: Advanced (collapsible)
        advanced_toggle = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TUNE, size=16, color=TEXT_MUTED),
                ft.Text("Tùy chọn nâng cao", size=13, color=TEXT_MUTED),
                ft.Icon(
                    ft.Icons.EXPAND_LESS if self._advanced_visible else ft.Icons.EXPAND_MORE,
                    size=16, color=TEXT_MUTED,
                ),
            ], spacing=6),
            on_click=self._toggle_advanced,
            ink=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        advanced_content = ft.Container(
            content=ft.Column([
                ft.Column([
                    ft.Text("Tốc độ dịch", size=13, color=TEXT_SECONDARY),
                    self._speed_mode,
                ], spacing=4),
                self._channel_field,
            ], spacing=12),
            visible=self._advanced_visible,
            padding=ft.padding.only(top=8),
        )

        section4 = ft.Container(
            content=ft.Column([
                advanced_toggle,
                advanced_content,
            ], spacing=0),
            **card_style(),
        )

        # Summary
        source_info = f"{self._state.source_type.upper()} │ {len(self._state.source_text):,} ký tự"
        summary = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_MUTED),
                ft.Text(f"Nguồn: {source_info} │ Tiêu đề: {self._state.title[:40]}", size=12, color=TEXT_MUTED),
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            bgcolor=BG_ELEVATED,
            border_radius=BUTTON_BORDER_RADIUS,
        )

        # Buttons
        buttons = ft.Row([
            outlined_button("← Quay lại", icon=ft.Icons.ARROW_BACK, on_click=self._on_back_click),
            ft.Container(expand=True),
            accent_button("Phân tích & Chia đoạn →", icon=ft.Icons.AUTO_FIX_HIGH, on_click=self._on_next_click),
        ])

        self.controls = [summary, section1, section2, section3, section4, buttons]

    def _toggle_advanced(self, e):
        self._advanced_visible = not self._advanced_visible
        self._build_controls()
        self._page.update()

    def _on_refresh_models(self, e):
        """Re-fetch models from 9Router."""
        self._model_source_text.value = "Đang fetch..."
        self._model_source_text.color = TEXT_MUTED
        self._page.update()

        def _fetch():
            models, source = _get_available_models()
            def _apply():
                self._available_models = models
                self._model_source = source
                self._model_source_text.value = source
                self._model_source_text.color = SUCCESS if "9Router" in source else DANGER

                # Update dropdown options, keep current values if still valid
                for dd in [self._model_analyzer_dd, self._model_translator_dd, self._model_reviewer_dd]:
                    old_val = dd.value
                    dd.options = [ft.dropdown.Option(m) for m in models]
                    dd.value = old_val if old_val in models else (models[0] if models else "")

                self._page.update()
                show_snackbar(self._page, f"Đã load {len(models)} models từ {source}")
            self._page.run_thread(_apply)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_save_defaults(self, e):
        """Save current model + advanced settings as defaults to DB."""
        set_setting(DB_KEY_MODEL_ANALYZER, self._model_analyzer_dd.value or DEFAULT_MODEL_ANALYZER)
        set_setting(DB_KEY_MODEL_TRANSLATOR, self._model_translator_dd.value or DEFAULT_MODEL_TRANSLATOR)
        set_setting(DB_KEY_MODEL_REVIEWER, self._model_reviewer_dd.value or DEFAULT_MODEL_REVIEWER)
        set_setting(DB_KEY_CHANNEL_NAME, self._channel_field.value or DEFAULT_CHANNEL)
        set_setting(DB_KEY_FAST_MODE, self._speed_mode.value or "safe")
        show_snackbar(self._page, "Đã lưu mặc định ✅")

    def _save_config(self):
        """Save current config to state."""
        speed = self._speed_mode.value or "safe"
        self._state.config = {
            "genre": self._genre_dd.value or "Đời thường",
            "audience": self._audience_dd.value or "Người lớn",
            "setting": self._setting_dd.value or "Hiện đại",
            "keigo": self._keigo_dd.value or "casual",
            "narrator": self._narrator_dd.value or "neutral",
            "style": self._style_dd.value or "podcast",
            "speed_mode": speed,
            "fast_mode": speed != "safe",  # backward compat
            "channel_name": self._channel_field.value or DEFAULT_CHANNEL,
            "max_retries": 2,
            "model_analyzer": self._model_analyzer_dd.value or DEFAULT_MODEL_ANALYZER,
            "model_translator": self._model_translator_dd.value or DEFAULT_MODEL_TRANSLATOR,
            "model_reviewer": self._model_reviewer_dd.value or DEFAULT_MODEL_REVIEWER,
        }

    def _on_back_click(self, e):
        self._save_config()
        if self._on_back:
            self._on_back()

    def _on_next_click(self, e):
        self._save_config()
        if self._on_next:
            self._on_next()

    def refresh(self):
        self._build_controls()

    def reset(self):
        self._genre_dd.value = "Đời thường"
        self._audience_dd.value = "Người lớn"
        self._setting_dd.value = "Hiện đại"
        self._keigo_dd.value = "casual"
        self._narrator_dd.value = "neutral"
        self._style_dd.value = "podcast"
        saved_speed = _load_saved(DB_KEY_FAST_MODE, "safe")
        # Backward compat: "true"→"balanced", "false"→"safe"
        if saved_speed == "true":
            saved_speed = "balanced"
        elif saved_speed == "false":
            saved_speed = "safe"
        self._speed_mode.value = saved_speed
        self._channel_field.value = _load_saved(DB_KEY_CHANNEL_NAME, DEFAULT_CHANNEL)
        self._model_analyzer_dd.value = _load_saved(DB_KEY_MODEL_ANALYZER, DEFAULT_MODEL_ANALYZER)
        self._model_translator_dd.value = _load_saved(DB_KEY_MODEL_TRANSLATOR, DEFAULT_MODEL_TRANSLATOR)
        self._model_reviewer_dd.value = _load_saved(DB_KEY_MODEL_REVIEWER, DEFAULT_MODEL_REVIEWER)
        self._advanced_visible = False
        self._build_controls()
