"""
Voice Generator Service — TTS engine with model management, queue processing,
batch generation, checkpoint, and SRT output.

Model auto-download from HuggingFace into core/ folder next to exe.
Supports queue of multiple stories, model loaded once for entire queue.
"""

import json
import os
import sys
import re
import time
import threading
import warnings

# Suppress noisy warnings from dependencies
warnings.filterwarnings("ignore", message=".*SoX.*")
warnings.filterwarnings("ignore", message=".*TripleDES.*")
os.environ["SOX_SUPPRESS_WARNING"] = "1"

# Lazy imports — numpy/soundfile only needed when actually generating voice
# This prevents crash on app startup if these are not installed
np = None
sf = None


def _ensure_audio_deps():
    """Lazy-load numpy and soundfile on first use."""
    global np, sf
    if np is None:
        import numpy
        np = numpy
    if sf is None:
        import soundfile
        sf = soundfile

# ─── Available Models ─────────────────────────────────────
AVAILABLE_MODELS = [
    {
        "id": "Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "hf_repo": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "label": "CustomVoice 1.7B (9 speakers, emotion)",
        "vram": "~4GB",
        "speakers": ["Serena", "Vivian", "Ryan", "Aiden", "Eric", "Dylan",
                      "uncle_fu", "ono_anna", "sohee"],
    },
    {
        "id": "Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "hf_repo": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "label": "CustomVoice 0.6B (nhẹ, 9 speakers)",
        "vram": "~2GB",
        "speakers": ["Serena", "Vivian", "Ryan", "Aiden", "Eric", "Dylan",
                      "uncle_fu", "ono_anna", "sohee"],
    },
    {
        "id": "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "hf_repo": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "label": "VoiceDesign 1.7B (tạo giọng mới)",
        "vram": "~4GB",
        "speakers": [],
    },
    {
        "id": "Qwen3-TTS-12Hz-1.7B-Base",
        "hf_repo": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "label": "Base 1.7B (voice clone)",
        "vram": "~4GB",
        "speakers": [],
    },
]

# Auto speaker mapping rules
AUTO_SPEAKER_RULES = {
    "narrator": "Serena",
    "default_female": "Vivian",
    "default_male": "Ryan",
    "default_mature_female": "Serena",
    "default_mature_male": "uncle_fu",
    "default_young_male": "Aiden",
}

BATCH_SIZE = 8
CHECKPOINT_EVERY = 50
SILENCE_BETWEEN = 0.3
SILENCE_SCENE_CHANGE = 0.8


# ─── Model Management ────────────────────────────────────

def get_core_dir() -> str:
    """Get core/ directory next to exe (or next to main.py in dev)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    core_dir = os.path.join(base, "core")
    os.makedirs(core_dir, exist_ok=True)
    return core_dir


def get_model_path(model_id: str) -> str:
    """Get local path for a model."""
    return os.path.join(get_core_dir(), model_id)


def is_model_downloaded(model_id: str) -> bool:
    """Check if model files exist locally."""
    path = get_model_path(model_id)
    return os.path.isdir(path) and os.path.exists(os.path.join(path, "config.json"))


def get_model_info(model_id: str) -> dict:
    """Get model metadata."""
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return {**m, "downloaded": is_model_downloaded(model_id),
                    "local_path": get_model_path(model_id)}
    return {}


def download_model(model_id: str, on_progress=None) -> str:
    """Download model from HuggingFace Hub. Returns local path.
    on_progress(message: str, progress: float 0-1)
    """
    info = get_model_info(model_id)
    if not info:
        raise ValueError(f"Unknown model: {model_id}")

    hf_repo = info["hf_repo"]
    local_path = get_model_path(model_id)

    if on_progress:
        on_progress(f"Đang tải {model_id}...", 0.0)

    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=hf_repo,
            local_dir=local_path,
            local_dir_use_symlinks=False,
        )
    except ImportError:
        # Fallback: install huggingface_hub
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub", "-q"])
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=hf_repo,
            local_dir=local_path,
            local_dir_use_symlinks=False,
        )

    if on_progress:
        on_progress(f"Tải xong {model_id}", 1.0)

    return local_path


# ─── Auto Speaker Mapping ────────────────────────────────

def auto_map_speakers(tts_segments: list, available_speakers: list) -> dict:
    """Auto-assign Qwen3-TTS speakers to story characters.
    Returns: {character_name: speaker_name}
    """
    # Collect unique speakers from segments
    characters = {}
    for seg in tts_segments:
        sp = seg.get("speaker", "narrator")
        if sp not in characters:
            characters[sp] = {"count": 0, "instructs": []}
        characters[sp]["count"] += 1
        inst = seg.get("instruct", "").lower()
        if inst and len(characters[sp]["instructs"]) < 5:
            characters[sp]["instructs"].append(inst)

    mapping = {}
    used_speakers = set()

    for char_name, info in characters.items():
        instructs = " ".join(info["instructs"])

        if char_name == "narrator":
            mapping[char_name] = "Serena"
            continue

        # Guess gender from instructs or name patterns
        is_female = any(w in instructs for w in ["female", "her ", "she ", "girl"])
        is_male = any(w in instructs for w in ["male", "his ", "he ", "boy", "man"])
        is_mature = any(w in instructs for w in ["mature", "old", "mother", "father", "stern"])

        # Japanese name heuristics
        if not is_female and not is_male:
            # Common female name endings
            if any(char_name.endswith(s) for s in ["こ", "み", "な", "か", "え"]):
                is_female = True
            else:
                is_male = True

        if is_female:
            if is_mature:
                pick = "Serena"
            else:
                pick = "Vivian"
        else:
            if is_mature:
                pick = "Ryan"
            else:
                pick = "Aiden"

        # Avoid duplicate speakers for different main characters
        if pick in used_speakers and pick != "Serena":
            alternatives = [s for s in available_speakers
                          if s not in used_speakers and s != "Serena"]
            if alternatives:
                pick = alternatives[0]

        mapping[char_name] = pick
        used_speakers.add(pick)

    return mapping


# ─── SRT Helper ───────────────────────────────────────────

def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(entries: list, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(f"{e['index']}\n")
            f.write(f"{_fmt_srt_time(e['start'])} --> {_fmt_srt_time(e['end'])}\n")
            if e.get("speaker", "narrator") != "narrator":
                f.write(f"[{e['speaker']}] {e['text']}\n")
            else:
                f.write(f"{e['text']}\n")
            f.write("\n")


# ─── Queue Item ───────────────────────────────────────────

class VoiceJob:
    """One story in the voice generation queue."""
    def __init__(self, title: str, tts_segments: list, source: str = "file",
                 source_path: str = "", speaker_map: dict = None):
        self.title = title
        self.tts_segments = tts_segments
        self.source = source          # "file" or "db"
        self.source_path = source_path
        self.speaker_map = speaker_map or {}
        self.status = "pending"       # pending / running / done / failed
        self.progress = 0.0
        self.output_wav = ""
        self.output_srt = ""
        self.error = ""


# ─── Voice Generator Engine ──────────────────────────────

class VoiceGeneratorEngine:
    """Processes a queue of VoiceJobs using Qwen3-TTS."""

    def __init__(self, on_progress=None, on_job_done=None,
                 on_queue_done=None, on_error=None, on_log=None):
        self.on_progress = on_progress or (lambda *a: None)
        self.on_job_done = on_job_done or (lambda *a: None)
        self.on_queue_done = on_queue_done or (lambda: None)
        self.on_error = on_error or (lambda *a: None)
        self.on_log = on_log or (lambda *a: None)

        self._model = None
        self._model_id = ""
        self._thread = None
        self._cancelled = False
        self._sample_rate = 24000

    def start(self, jobs: list, model_id: str, output_dir: str):
        """Start processing job queue in background thread."""
        self._cancelled = False
        self._thread = threading.Thread(
            target=self._run_queue, args=(jobs, model_id, output_dir),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancelled = True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, msg: str):
        self.on_log(time.strftime("%H:%M:%S"), msg)

    def _clear_gpu(self):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _load_model(self, model_id: str):
        """Load model (or reuse if same model already loaded)."""
        if self._model and self._model_id == model_id:
            self._log(f"Model {model_id} đã loaded, reuse")
            return

        model_path = get_model_path(model_id)
        if not is_model_downloaded(model_id):
            raise FileNotFoundError(f"Model chưa tải: {model_id}")

        self._log(f"Loading {model_id}...")
        import torch
        from qwen_tts import Qwen3TTSModel

        self._model = Qwen3TTSModel.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        self._model_id = model_id
        self._log(f"Model loaded")

    def _run_queue(self, jobs: list, model_id: str, output_dir: str):
        """Process all jobs sequentially with single model load."""
        _ensure_audio_deps()
        os.makedirs(output_dir, exist_ok=True)

        try:
            self._load_model(model_id)
        except Exception as e:
            self.on_error(f"Không thể load model: {e}")
            return

        for job_idx, job in enumerate(jobs):
            if self._cancelled:
                break

            job.status = "running"
            self._log(f"[{job_idx+1}/{len(jobs)}] {job.title} ({len(job.tts_segments)} segments)")
            self.on_progress(job_idx, len(jobs), 0, f"Bắt đầu: {job.title}")

            try:
                self._process_job(job, job_idx, len(jobs), output_dir)
                job.status = "done"
                self.on_job_done(job_idx, job)
                self._log(f"[{job_idx+1}/{len(jobs)}] ✅ {job.title} → {job.output_wav}")
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                self._log(f"[{job_idx+1}/{len(jobs)}] ❌ {job.title}: {e}")
                self.on_error(f"Job '{job.title}' lỗi: {e}")

        self._log("Queue hoàn tất")
        self.on_queue_done()

    def _process_job(self, job: VoiceJob, job_idx: int, total_jobs: int, output_dir: str):
        """Generate voice for one story with checkpoints."""
        segments = job.tts_segments
        speaker_map = job.speaker_map
        total = len(segments)

        # Create job directory + checkpoints
        safe_title = re.sub(r'[^\w\s-]', '', job.title).strip()[:50] or "output"
        job_dir = os.path.join(output_dir, safe_title)
        ckpt_dir = os.path.join(job_dir, "checkpoints")
        os.makedirs(ckpt_dir, exist_ok=True)

        # Check for existing checkpoint (resume support)
        progress_file = os.path.join(ckpt_dir, "progress.json")
        wav_results = {}
        seg_durations = {}
        gen_time = 0

        if os.path.exists(progress_file):
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                # Load saved durations
                dur_file = os.path.join(ckpt_dir, "durations.json")
                if os.path.exists(dur_file):
                    with open(dur_file, "r", encoding="utf-8") as f:
                        seg_durations = {int(k): v for k, v in json.load(f).items()}
                self._log(f"  Resume: {len(seg_durations)} segments từ checkpoint")
            except Exception:
                pass

        # Group by speaker for batch efficiency
        speaker_groups = {}
        for i, seg in enumerate(segments):
            if i in seg_durations:
                continue  # Skip already generated segments
            text = seg.get("text", "").strip()
            if not text:
                continue
            char_name = seg.get("speaker", "narrator")
            speaker = speaker_map.get(char_name, "Serena")
            if speaker not in speaker_groups:
                speaker_groups[speaker] = []
            speaker_groups[speaker].append({
                "idx": i, "text": text,
                "instruct": seg.get("instruct", "natural and clear"),
                "char_name": char_name,
            })

        if not speaker_groups and not seg_durations:
            raise ValueError("Không có segment nào để generate")

        # Generate batches
        chunk_id = 0
        segs_since_checkpoint = 0

        for speaker, items in speaker_groups.items():
            if self._cancelled:
                return

            self._log(f"  Speaker: {speaker} ({len(items)} segs)")

            for batch_start in range(0, len(items), BATCH_SIZE):
                if self._cancelled:
                    return

                batch = items[batch_start:batch_start + BATCH_SIZE]
                texts = [b["text"] for b in batch]
                instructs = [b["instruct"] for b in batch]
                indices = [b["idx"] for b in batch]

                try:
                    t1 = time.time()
                    wavs, sr = self._model.generate_custom_voice(
                        text=texts, speaker=speaker,
                        instruct=instructs, language="Auto",
                    )
                    gt = time.time() - t1
                    gen_time += gt
                    self._sample_rate = sr

                    for j, wav in enumerate(wavs):
                        if wav is not None and len(wav) > 0:
                            wav_results[indices[j]] = wav
                            seg_durations[indices[j]] = len(wav) / sr
                            segs_since_checkpoint += 1

                except Exception as e:
                    self._log(f"    Batch error: {e}, fallback 1-by-1")
                    for b in batch:
                        try:
                            ws, sr = self._model.generate_custom_voice(
                                text=b["text"], speaker=speaker,
                                instruct=b["instruct"], language="Auto",
                            )
                            self._sample_rate = sr
                            if ws and len(ws[0]) > 0:
                                wav_results[b["idx"]] = ws[0]
                                seg_durations[b["idx"]] = len(ws[0]) / sr
                                segs_since_checkpoint += 1
                        except Exception:
                            pass

                self._clear_gpu()

                # Progress
                done = len(seg_durations)
                progress = done / total if total > 0 else 0
                job.progress = progress
                self.on_progress(job_idx, total_jobs, progress,
                                 f"{done}/{total} segments")

                # Checkpoint save every CHECKPOINT_EVERY segments
                if segs_since_checkpoint >= CHECKPOINT_EVERY:
                    self._save_checkpoint(ckpt_dir, chunk_id, wav_results,
                                          seg_durations, segments, total, gen_time)
                    chunk_id += 1
                    segs_since_checkpoint = 0
                    # Free memory for saved wavs
                    wav_results = {}

        # Final checkpoint
        if wav_results:
            self._save_checkpoint(ckpt_dir, chunk_id, wav_results,
                                  seg_durations, segments, total, gen_time)

        # Combine all checkpoint chunks into final WAV
        sr = self._sample_rate
        self._log(f"  Combining checkpoints...")

        # Re-read all per-segment wavs from checkpoints or memory
        # Easiest: combine chunk WAVs in order
        chunk_files = sorted(
            [os.path.join(ckpt_dir, f) for f in os.listdir(ckpt_dir)
             if f.startswith("chunk_") and f.endswith(".wav")]
        )

        if chunk_files:
            all_audio = []
            for cf in chunk_files:
                data, _ = sf.read(cf)
                all_audio.append(data)
            final_audio = np.concatenate(all_audio)
        else:
            raise ValueError("Không có checkpoint audio")

        # Save final WAV
        wav_path = os.path.join(job_dir, f"{safe_title}.wav")
        sf.write(wav_path, final_audio, sr)
        job.output_wav = wav_path

        # Build SRT from durations
        srt_entries = []
        current_time = 0.0
        srt_idx = 1
        prev_char = None
        for i in range(total):
            if i not in seg_durations:
                continue
            char_name = segments[i].get("speaker", "narrator")
            text = segments[i].get("text", "").strip()
            if not text:
                continue

            if prev_char is not None and prev_char != char_name:
                current_time += SILENCE_SCENE_CHANGE
            elif prev_char is not None:
                current_time += SILENCE_BETWEEN

            dur = seg_durations[i]
            srt_entries.append({
                "index": srt_idx, "start": current_time,
                "end": current_time + dur, "speaker": char_name, "text": text,
            })
            srt_idx += 1
            current_time += dur
            prev_char = char_name

        srt_path = os.path.join(job_dir, f"{safe_title}.srt")
        write_srt(srt_entries, srt_path)
        job.output_srt = srt_path

        self._log(f"  Output: {wav_path} ({len(final_audio)/sr:.0f}s) + SRT ({len(srt_entries)} entries)")
        self._log(f"  Checkpoints: {len(chunk_files)} files in {ckpt_dir}")

    def _save_checkpoint(self, ckpt_dir: str, chunk_id: int, wav_results: dict,
                         seg_durations: dict, segments: list, total: int, gen_time: float):
        """Save checkpoint: chunk WAV + progress + durations."""
        sr = self._sample_rate

        # Build chunk WAV in original order from current wav_results
        combined = []
        prev_char = None
        for i in sorted(wav_results.keys()):
            char_name = segments[i].get("speaker", "narrator")
            if prev_char is not None and prev_char != char_name:
                combined.append(np.zeros(int(sr * SILENCE_SCENE_CHANGE), dtype=np.float32))
            elif prev_char is not None:
                combined.append(np.zeros(int(sr * SILENCE_BETWEEN), dtype=np.float32))
            combined.append(wav_results[i].astype(np.float32))
            prev_char = char_name

        if combined:
            chunk_audio = np.concatenate(combined)
            chunk_path = os.path.join(ckpt_dir, f"chunk_{chunk_id:04d}.wav")
            sf.write(chunk_path, chunk_audio, sr)
            chunk_dur = len(chunk_audio) / sr
            self._log(f"  >> Checkpoint #{chunk_id}: {chunk_dur:.0f}s saved")

        # Save progress
        progress_file = os.path.join(ckpt_dir, "progress.json")
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump({
                "completed": len(seg_durations),
                "total": total,
                "gen_time": gen_time,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, indent=2)

        # Save durations for resume
        dur_file = os.path.join(ckpt_dir, "durations.json")
        with open(dur_file, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in seg_durations.items()}, f)
