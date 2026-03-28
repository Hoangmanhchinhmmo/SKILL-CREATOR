"""
Voice Generator Tab — Batch TTS generation with model management.
4 sections: Model, Queue, Speaker Mapping, Progress.
"""

import json
import os
import threading
import time

import flet as ft
from theme import (
    BG_PRIMARY, BG_CARD, BG_ELEVATED, BORDER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, ACCENT,
    SUCCESS, DANGER, INFO, WARNING,
    card_style, accent_button, outlined_button, danger_button, show_snackbar,
    show_dialog, close_dialog,
    input_field, CARD_BORDER_RADIUS, BUTTON_BORDER_RADIUS,
)
from services.voice_generator import (
    AVAILABLE_MODELS, get_model_info, is_model_downloaded, download_model,
    get_core_dir, auto_map_speakers, VoiceJob, VoiceGeneratorEngine,
)


DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "TTS-Output")


class VoiceTab(ft.Column):
    """Voice Generator tab — batch TTS with queue."""

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self._page = page

        # State
        self._selected_model = AVAILABLE_MODELS[0]["id"]
        self._jobs: list[VoiceJob] = []
        self._selected_job_idx: int = -1
        self._output_dir = DEFAULT_OUTPUT_DIR
        self._engine: VoiceGeneratorEngine = None
        self._is_running = False
        self._start_time = 0

        # UI refs
        self._model_status = ft.Text("", size=12, color=TEXT_MUTED)
        self._model_progress = ft.ProgressBar(value=0, color=ACCENT, bgcolor=BORDER, visible=False)
        self._queue_list = ft.Column(spacing=6)
        self._mapping_section = ft.Column(spacing=4)
        self._progress_bar = ft.ProgressBar(value=0, color=ACCENT, bgcolor=BORDER, visible=False)
        self._progress_text = ft.Text("", size=12, color=TEXT_MUTED)
        self._timer_text = ft.Text("", size=13, color=TEXT_SECONDARY)
        self._log_list = ft.ListView(spacing=2, height=120, auto_scroll=True)

        self._build()
        self._check_model_status()

    def _build(self):
        self.controls = [
            self._build_model_section(),
            self._build_queue_section(),
            self._build_mapping_section(),
            self._build_progress_section(),
        ]

    # ─── Section 1: Model ─────────────────────────────────

    def _build_model_section(self) -> ft.Container:
        model_options = [ft.dropdown.Option(m["id"], text=m["label"]) for m in AVAILABLE_MODELS]

        self._model_dd = ft.Dropdown(
            value=self._selected_model,
            options=model_options,
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
            border_color=BORDER, focused_border_color=ACCENT,
            border_radius=BUTTON_BORDER_RADIUS,
            width=400,
        )
        self._model_dd.on_change = self._on_model_change

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MEMORY, size=18, color=ACCENT),
                    ft.Text("Model TTS", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Divider(height=1, color=BORDER),
                ft.Row([
                    self._model_dd,
                    ft.Container(width=8),
                    accent_button("Tải model", icon=ft.Icons.DOWNLOAD,
                                  on_click=self._on_download_model),
                ], spacing=8),
                self._model_status,
                self._model_progress,
            ], spacing=8),
            **card_style(),
        )

    def _check_model_status(self):
        info = get_model_info(self._selected_model)
        if info.get("downloaded"):
            self._model_status.value = f"✅ Sẵn sàng │ {info.get('vram', '')} │ {len(info.get('speakers', []))} speakers │ {info.get('local_path', '')}"
            self._model_status.color = SUCCESS
        else:
            self._model_status.value = f"⬇ Chưa tải │ Nhấn 'Tải model' để download từ HuggingFace"
            self._model_status.color = WARNING

    def _on_model_change(self, e):
        self._selected_model = e.control.value
        self._check_model_status()
        self._page.update()

    def _on_download_model(self, e):
        model_id = self._selected_model
        if is_model_downloaded(model_id):
            show_snackbar(self._page, f"Model {model_id} đã có sẵn")
            return

        self._model_progress.visible = True
        self._model_status.value = f"Đang tải {model_id}... (có thể mất 5-10 phút)"
        self._model_status.color = INFO
        self._page.update()

        def _download():
            try:
                download_model(model_id)
                def _done():
                    self._model_progress.visible = False
                    self._check_model_status()
                    self._page.update()
                    show_snackbar(self._page, f"✅ Đã tải {model_id}")
                self._page.run_thread(_done)
            except Exception as ex:
                def _err():
                    self._model_progress.visible = False
                    self._model_status.value = f"❌ Lỗi tải: {ex}"
                    self._model_status.color = DANGER
                    self._page.update()
                self._page.run_thread(_err)

        threading.Thread(target=_download, daemon=True).start()

    # ─── Section 2: Queue ─────────────────────────────────

    def _build_queue_section(self) -> ft.Container:
        self._output_field = input_field(
            label="Thư mục output",
            value=self._output_dir,
            expand=True,
        )
        self._output_field.on_blur = lambda e: setattr(self, '_output_dir', e.control.value)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.QUEUE_MUSIC, size=18, color=ACCENT),
                    ft.Text("Hàng đợi", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    outlined_button("+ Từ lịch sử", icon=ft.Icons.HISTORY,
                                    on_click=self._on_add_from_history),
                    outlined_button("+ Import JSON", icon=ft.Icons.FOLDER_OPEN,
                                    on_click=self._on_add_from_file),
                ], spacing=8),
                ft.Divider(height=1, color=BORDER),
                self._queue_list,
                ft.Row([self._output_field], spacing=8),
            ], spacing=8),
            **card_style(),
        )

    def _rebuild_queue_list(self):
        self._queue_list.controls.clear()
        if not self._jobs:
            self._queue_list.controls.append(
                ft.Text("Chưa có truyện. Thêm từ lịch sử hoặc import JSON.",
                        size=12, color=TEXT_MUTED, italic=True))
            return

        for i, job in enumerate(self._jobs):
            status_map = {"pending": ("⏳", TEXT_MUTED), "running": ("⟳", INFO),
                         "done": ("✅", SUCCESS), "failed": ("❌", DANGER)}
            icon, color = status_map.get(job.status, ("⏳", TEXT_MUTED))
            is_selected = i == self._selected_job_idx

            card = ft.Container(
                content=ft.Row([
                    ft.Text(f"#{i+1}", size=12, color=TEXT_MUTED, width=25),
                    ft.Text(icon, size=14),
                    ft.Text(job.title[:35], size=13, color=TEXT_PRIMARY,
                            weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.NORMAL,
                            expand=True),
                    ft.Text(f"{len(job.tts_segments)} segs", size=11, color=TEXT_MUTED),
                    ft.Text(job.source, size=10, color=TEXT_MUTED),
                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=DANGER,
                                  tooltip="Xóa",
                                  on_click=lambda e, idx=i: self._remove_job(idx)),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=BG_ELEVATED if is_selected else BG_PRIMARY,
                border=ft.border.all(1, ACCENT if is_selected else BORDER),
                border_radius=BUTTON_BORDER_RADIUS,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                on_click=lambda e, idx=i: self._select_job(idx),
                ink=True,
            )
            self._queue_list.controls.append(card)

    def _on_add_from_history(self, e):
        """Show dialog to pick translations with TTS data."""
        from db.models import list_translations
        items, _ = list_translations(per_page=20)

        if not items:
            show_snackbar(self._page, "Chưa có bài dịch nào", bgcolor=WARNING)
            return

        options = []
        for item in items:
            tid = item["id"]
            title = item.get("title", "Untitled")
            status = item.get("status", "")
            # Check if has TTS data
            from db.models import get_translation
            t = get_translation(tid)
            tts_col = t.get("tts_json", "") if t else ""
            has_tts = bool(tts_col and tts_col.strip().startswith("["))
            if not has_tts:
                # Check embedded marker
                result = t.get("result_text", "") if t else ""
                has_tts = "<!-- TTS_SEGMENTS -->" in result

            label = f"#{tid} {title[:30]}"
            if has_tts:
                label += " [TTS ✅]"
            else:
                label += " [no TTS]"

            options.append(ft.dropdown.Option(key=str(tid), text=label))

        dd = ft.Dropdown(options=options, bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
                         border_color=BORDER, width=400, label="Chọn bài dịch",
                         )

        def _add(e):
            tid = int(dd.value) if dd.value else None
            if tid:
                self._add_job_from_db(tid)
            close_dialog(self._page, dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Chọn bài dịch có TTS data"),
            content=ft.Column([dd], height=80),
            actions=[
                ft.TextButton("Hủy", on_click=lambda e: close_dialog(self._page, dlg)),
                ft.TextButton("Thêm", on_click=_add),
            ],
        )
        show_dialog(self._page, dlg)

    def _add_job_from_db(self, translation_id: int):
        """Load TTS segments from DB translation."""
        from db.models import get_translation
        import re as _re
        t = get_translation(translation_id)
        if not t:
            show_snackbar(self._page, "Không tìm thấy bài dịch", bgcolor=DANGER)
            return

        tts_segments = []
        tts_col = t.get("tts_json", "")
        if tts_col and tts_col.strip().startswith("["):
            tts_segments = json.loads(tts_col)
        else:
            result = t.get("result_text", "")
            if "<!-- TTS_SEGMENTS -->" in result:
                parts = result.split("<!-- TTS_SEGMENTS -->", 1)
                match = _re.search(r"\[[\s\S]*\]", parts[1])
                if match:
                    tts_segments = json.loads(match.group())

        if not tts_segments:
            show_snackbar(self._page, "Bài dịch không có TTS data. Bật TTS Director khi dịch.",
                          bgcolor=WARNING)
            return

        title = t.get("title", f"Bài dịch #{translation_id}")
        info = get_model_info(self._selected_model)
        speakers = info.get("speakers", [])
        speaker_map = auto_map_speakers(tts_segments, speakers)

        job = VoiceJob(title=title, tts_segments=tts_segments, source="db",
                       source_path=f"DB #{translation_id}", speaker_map=speaker_map)
        self._jobs.append(job)
        self._selected_job_idx = len(self._jobs) - 1
        self._rebuild_queue_list()
        self._rebuild_mapping()
        self._build()
        self._page.update()
        show_snackbar(self._page, f"Đã thêm: {title} ({len(tts_segments)} segments)")

    def _on_add_from_file(self, e):
        """Show dialog to input JSON file path manually."""
        path_field = ft.TextField(
            label="Đường dẫn file hoặc thư mục JSON",
            hint_text=r"VD: D:\demo\tts.json hoặc D:\demo\ (load tất cả .json)",
            bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
            border_color=BORDER, expand=True,
        )

        def _add(ev):
            path = (path_field.value or "").strip()
            close_dialog(self._page, dlg)
            if not path:
                return
            if os.path.isdir(path):
                # Load all JSON files in directory
                count = 0
                for fname in sorted(os.listdir(path)):
                    if fname.endswith(".json"):
                        self._add_job_from_file(os.path.join(path, fname))
                        count += 1
                if count == 0:
                    show_snackbar(self._page, "Không tìm thấy file .json trong thư mục", bgcolor=WARNING)
            elif os.path.isfile(path):
                self._add_job_from_file(path)
            else:
                show_snackbar(self._page, f"Không tìm thấy: {path}", bgcolor=DANGER)
                return
            self._rebuild_queue_list()
            self._rebuild_mapping()
            self._build()
            self._page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Import TTS JSON"),
            content=ft.Column([path_field], height=80, width=500),
            actions=[
                ft.TextButton("Hủy", on_click=lambda ev: close_dialog(self._page, dlg)),
                ft.TextButton("Thêm", on_click=_add),
            ],
        )
        show_dialog(self._page, dlg)

    def _add_job_from_file(self, file_path: str):
        """Load TTS segments from JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tts_segments = json.load(f)
            if not isinstance(tts_segments, list) or not tts_segments:
                show_snackbar(self._page, f"File không hợp lệ: {os.path.basename(file_path)}",
                              bgcolor=DANGER)
                return
        except Exception as ex:
            show_snackbar(self._page, f"Lỗi đọc file: {ex}", bgcolor=DANGER)
            return

        title = os.path.splitext(os.path.basename(file_path))[0]
        info = get_model_info(self._selected_model)
        speakers = info.get("speakers", [])
        speaker_map = auto_map_speakers(tts_segments, speakers)

        job = VoiceJob(title=title, tts_segments=tts_segments, source="file",
                       source_path=file_path, speaker_map=speaker_map)
        self._jobs.append(job)
        self._selected_job_idx = len(self._jobs) - 1
        show_snackbar(self._page, f"Đã thêm: {title} ({len(tts_segments)} segments)")

    def _remove_job(self, idx: int):
        if 0 <= idx < len(self._jobs) and self._jobs[idx].status == "pending":
            self._jobs.pop(idx)
            if self._selected_job_idx >= len(self._jobs):
                self._selected_job_idx = len(self._jobs) - 1
            self._rebuild_queue_list()
            self._rebuild_mapping()
            self._build()
            self._page.update()

    def _select_job(self, idx: int):
        self._selected_job_idx = idx
        self._rebuild_queue_list()
        self._rebuild_mapping()
        self._build()
        self._page.update()

    # ─── Section 3: Speaker Mapping ───────────────────────

    def _build_mapping_section(self) -> ft.Container:
        self._rebuild_mapping()
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.PEOPLE, size=18, color=ACCENT),
                    ft.Text("Speaker Mapping", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ], spacing=8),
                ft.Divider(height=1, color=BORDER),
                self._mapping_section,
            ], spacing=8),
            **card_style(),
        )

    def _rebuild_mapping(self):
        self._mapping_section.controls.clear()
        if self._selected_job_idx < 0 or self._selected_job_idx >= len(self._jobs):
            self._mapping_section.controls.append(
                ft.Text("Chọn truyện từ hàng đợi để xem/sửa speaker mapping",
                        size=12, color=TEXT_MUTED, italic=True))
            return

        job = self._jobs[self._selected_job_idx]
        info = get_model_info(self._selected_model)
        speakers = info.get("speakers", [])

        self._mapping_section.controls.append(
            ft.Text(f"Truyện: {job.title}", size=13, color=TEXT_SECONDARY))

        # Header
        self._mapping_section.controls.append(ft.Row([
            ft.Text("Nhân vật", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD, expand=2),
            ft.Text("Số đoạn", size=11, color=TEXT_MUTED, width=60),
            ft.Text("Speaker", size=11, color=TEXT_MUTED, weight=ft.FontWeight.BOLD, expand=2),
        ], spacing=8))

        # Count segments per character
        char_counts = {}
        for seg in job.tts_segments:
            sp = seg.get("speaker", "narrator")
            char_counts[sp] = char_counts.get(sp, 0) + 1

        for char_name, count in sorted(char_counts.items(), key=lambda x: -x[1]):
            current_speaker = job.speaker_map.get(char_name, "Serena")
            dd = ft.Dropdown(
                value=current_speaker,
                options=[ft.dropdown.Option(s) for s in speakers] if speakers else [ft.dropdown.Option("N/A")],
                bgcolor=BG_ELEVATED, color=TEXT_PRIMARY,
                border_color=BORDER, border_radius=4,
                content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
                text_size=12, expand=2, height=40,
            )
            dd.on_change = lambda e, cn=char_name: self._on_speaker_change(cn, e.control.value)
            self._mapping_section.controls.append(ft.Row([
                ft.Text(char_name, size=13, color=TEXT_PRIMARY, expand=2),
                ft.Text(str(count), size=12, color=TEXT_MUTED, width=60),
                dd,
            ], spacing=8))

    def _on_speaker_change(self, char_name: str, speaker: str):
        if 0 <= self._selected_job_idx < len(self._jobs):
            self._jobs[self._selected_job_idx].speaker_map[char_name] = speaker

    # ─── Section 4: Progress ──────────────────────────────

    def _build_progress_section(self) -> ft.Container:
        if self._is_running:
            action_row = ft.Row([
                danger_button("Dừng", icon=ft.Icons.STOP, on_click=self._on_stop),
            ])
        else:
            action_row = ft.Row([
                accent_button("Bắt đầu tạo voice", icon=ft.Icons.PLAY_ARROW,
                              on_click=self._on_start),
            ])

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MULTITRACK_AUDIO, size=18, color=ACCENT),
                    ft.Text("Tiến trình", size=15, color=TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    self._timer_text,
                ], spacing=8),
                ft.Divider(height=1, color=BORDER),
                self._progress_bar,
                self._progress_text,
                ft.Container(
                    content=self._log_list,
                    bgcolor=BG_PRIMARY,
                    border_radius=BUTTON_BORDER_RADIUS,
                    border=ft.border.all(1, BORDER),
                    padding=8,
                ),
                action_row,
            ], spacing=8),
            **card_style(),
        )

    def _on_start(self, e):
        pending = [j for j in self._jobs if j.status == "pending"]
        if not pending:
            show_snackbar(self._page, "Không có truyện nào trong hàng đợi", bgcolor=WARNING)
            return

        if not is_model_downloaded(self._selected_model):
            show_snackbar(self._page, "Chưa tải model! Nhấn 'Tải model' trước.", bgcolor=DANGER)
            return

        self._is_running = True
        self._start_time = time.time()
        self._progress_bar.visible = True
        self._progress_bar.value = 0
        self._log_list.controls.clear()

        self._engine = VoiceGeneratorEngine(
            on_progress=self._on_progress,
            on_job_done=self._on_job_done,
            on_queue_done=self._on_queue_done,
            on_error=self._on_engine_error,
            on_log=self._on_log,
        )

        os.makedirs(self._output_dir, exist_ok=True)
        self._engine.start(pending, self._selected_model, self._output_dir)
        self._start_timer()
        self._build()
        self._page.update()

    def _on_stop(self, e):
        if self._engine:
            self._engine.cancel()
        self._is_running = False
        self._build()
        self._page.update()
        show_snackbar(self._page, "Đã dừng")

    def _start_timer(self):
        def _tick():
            while self._is_running:
                elapsed = time.time() - self._start_time
                m, s = int(elapsed // 60), int(elapsed % 60)
                try:
                    self._timer_text.value = f"⏱ {m:02d}:{s:02d}"
                    self._page.update()
                except Exception:
                    break
                time.sleep(1)
        threading.Thread(target=_tick, daemon=True).start()

    def _on_progress(self, job_idx, total_jobs, progress, message):
        def _apply():
            try:
                self._progress_bar.value = progress
                self._progress_text.value = f"Truyện {job_idx+1}/{total_jobs} │ {message}"
                self._rebuild_queue_list()
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_job_done(self, job_idx, job):
        def _apply():
            try:
                self._rebuild_queue_list()
                self._page.update()
                show_snackbar(self._page, f"✅ {job.title} → {os.path.basename(job.output_wav)}")
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_queue_done(self):
        def _apply():
            try:
                self._is_running = False
                self._progress_bar.value = 1.0
                elapsed = time.time() - self._start_time
                m, s = int(elapsed // 60), int(elapsed % 60)
                self._progress_text.value = f"Hoàn tất trong {m}m {s}s"
                self._timer_text.value = f"⏱ {m:02d}:{s:02d}"
                self._rebuild_queue_list()
                self._build()
                self._page.update()
                show_snackbar(self._page, "✅ Queue hoàn tất!")
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_engine_error(self, message):
        def _apply():
            try:
                show_snackbar(self._page, f"Lỗi: {message}", bgcolor=DANGER)
            except Exception:
                pass
        self._page.run_thread(_apply)

    def _on_log(self, timestamp, message):
        def _apply():
            try:
                self._log_list.controls.append(
                    ft.Text(f"[{timestamp}] {message}", size=11, color=TEXT_MUTED,
                            font_family="Consolas"))
                self._page.update()
            except Exception:
                pass
        self._page.run_thread(_apply)

    def refresh(self):
        self._check_model_status()
        self._rebuild_queue_list()
        self._build()
