"""
yt-dlp Manager — Download, auto-update, and extract subtitles.
Binary stored in %APPDATA%/NPB-Podcast-Writer/yt-dlp.exe
"""

import os
import re
import json
import subprocess
import tempfile
import threading

import requests

APP_DATA_DIR = "NPB-Podcast-Writer"
YTDLP_FILENAME = "yt-dlp.exe"
VERSION_FILENAME = "ytdlp_version.txt"
GITHUB_LATEST_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
SUBTITLE_LANG_PRIORITY = ["vi", "ko", "ja", "en"]

_update_lock = threading.Lock()
_update_status = {"checking": False, "message": "", "version": ""}


def _get_data_dir() -> str:
    """Get persistent data directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        data_dir = os.path.join(appdata, APP_DATA_DIR)
    else:
        data_dir = os.path.join(os.path.expanduser("~"), f".{APP_DATA_DIR}")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_ytdlp_path() -> str:
    """Get path to yt-dlp.exe. Downloads if not present."""
    data_dir = _get_data_dir()
    exe_path = os.path.join(data_dir, YTDLP_FILENAME)
    if not os.path.exists(exe_path):
        _download_ytdlp(exe_path)
    return exe_path


def get_local_version() -> str:
    """Get locally stored yt-dlp version."""
    version_path = os.path.join(_get_data_dir(), VERSION_FILENAME)
    if os.path.exists(version_path):
        with open(version_path, "r") as f:
            return f.read().strip()
    return ""


def get_update_status() -> dict:
    """Get current update status for UI display."""
    return dict(_update_status)


def check_and_update_async(on_status=None):
    """Check for updates and download if available. Runs in background thread.
    on_status(message: str) callback for UI updates.
    """
    def _worker():
        with _update_lock:
            if _update_status["checking"]:
                return
            _update_status["checking"] = True

        try:
            _notify(on_status, "Đang kiểm tra yt-dlp...")
            exe_path = os.path.join(_get_data_dir(), YTDLP_FILENAME)

            # Download if not exists
            if not os.path.exists(exe_path):
                _notify(on_status, "Đang tải yt-dlp lần đầu...")
                _download_ytdlp(exe_path)
                _notify(on_status, f"yt-dlp đã cài đặt ✅")
                return

            # Check for update
            local_ver = get_local_version()
            try:
                resp = requests.get(GITHUB_LATEST_URL, timeout=10)
                resp.raise_for_status()
                release = resp.json()
                remote_ver = release.get("tag_name", "")
            except Exception:
                _notify(on_status, f"yt-dlp {local_ver} (offline)")
                return

            if remote_ver and remote_ver != local_ver:
                _notify(on_status, f"Đang cập nhật yt-dlp → {remote_ver}...")
                _download_ytdlp(exe_path, release=release)
                _notify(on_status, f"yt-dlp {remote_ver} ✅")
            else:
                _notify(on_status, f"yt-dlp {local_ver} ✅")

        except Exception as e:
            _notify(on_status, f"yt-dlp lỗi: {e}")
        finally:
            _update_status["checking"] = False

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def _notify(callback, message: str):
    """Update status and call callback."""
    _update_status["message"] = message
    if callback:
        try:
            callback(message)
        except Exception:
            pass


def _download_ytdlp(exe_path: str, release: dict = None):
    """Download yt-dlp.exe from GitHub releases."""
    if release is None:
        resp = requests.get(GITHUB_LATEST_URL, timeout=15)
        resp.raise_for_status()
        release = resp.json()

    version = release.get("tag_name", "unknown")
    assets = release.get("assets", [])

    # Find yt-dlp.exe asset
    download_url = None
    for asset in assets:
        if asset.get("name") == "yt-dlp.exe":
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        raise RuntimeError("Không tìm thấy yt-dlp.exe trong release")

    # Download to temp then move
    tmp_path = exe_path + ".tmp"
    resp = requests.get(download_url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    # Replace
    if os.path.exists(exe_path):
        try:
            os.remove(exe_path)
        except OSError:
            pass
    os.rename(tmp_path, exe_path)

    # Save version
    version_path = os.path.join(os.path.dirname(exe_path), VERSION_FILENAME)
    with open(version_path, "w") as f:
        f.write(version)

    _update_status["version"] = version


def get_video_info(url: str) -> dict | None:
    """Get video metadata (title, duration, available subtitles)."""
    exe = get_ytdlp_path()
    try:
        result = subprocess.run(
            [exe, "--dump-json", "--no-download", url],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return {
                "title": data.get("title", ""),
                "duration": data.get("duration", 0),
                "duration_string": data.get("duration_string", ""),
                "subtitles": list(data.get("subtitles", {}).keys()),
                "auto_subtitles": list(data.get("automatic_captions", {}).keys()),
            }
    except Exception:
        pass
    return None


def extract_subtitle(url: str, lang: str = None) -> dict:
    """Extract subtitle text from YouTube video.
    Returns {"text": str, "lang": str}.
    """
    exe = get_ytdlp_path()
    tmpdir = tempfile.mkdtemp(prefix="npb_sub_")

    lang_list = [lang] if lang else SUBTITLE_LANG_PRIORITY
    lang_str = ",".join(lang_list)

    try:
        # Try manual subtitles first, then auto-generated
        output_template = os.path.join(tmpdir, "subtitle")

        result = subprocess.run(
            [
                exe,
                "--write-sub", "--write-auto-sub",
                "--sub-lang", lang_str,
                "--skip-download",
                "--sub-format", "vtt/srt/best",
                "-o", output_template,
                url,
            ],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        # Find downloaded subtitle file
        sub_text = ""
        sub_lang = ""
        for fname in os.listdir(tmpdir):
            if fname.endswith((".vtt", ".srt")):
                fpath = os.path.join(tmpdir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = f.read()
                sub_text = _parse_subtitle(raw)
                # Extract lang from filename like subtitle.vi.vtt
                parts = fname.rsplit(".", 2)
                if len(parts) >= 3:
                    sub_lang = parts[-2]
                break

        return {"text": sub_text, "lang": sub_lang}

    finally:
        # Cleanup temp files
        try:
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)
        except OSError:
            pass


def _parse_subtitle(raw: str) -> str:
    """Parse VTT/SRT subtitle to plain text. Remove timestamps and duplicates."""
    lines = raw.split("\n")
    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        # Skip VTT header
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        # Skip timestamps (00:00:00.000 --> 00:00:05.000)
        if re.match(r"^\d{2}:\d{2}[:\.]", line):
            continue
        # Skip sequence numbers
        if re.match(r"^\d+$", line):
            continue
        # Skip empty
        if not line:
            continue
        # Remove VTT tags like <c>, </c>, <00:00:01.000>
        line = re.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            text_lines.append(line)

    return "\n".join(text_lines)
