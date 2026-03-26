"""
Auto-Update Service — Check for new versions and download.
"""

import os
import subprocess
import tempfile
import requests

from db.models import get_setting

def _read_version() -> str:
    """Read version from VERSION file."""
    for path in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION"),
        os.path.join(os.path.dirname(os.path.abspath(__import__("sys").executable)), "VERSION"),
    ]:
        if os.path.isfile(path):
            with open(path, "r") as f:
                return f.read().strip()
    return "3.0.0"

APP_VERSION = _read_version()
DEFAULT_UPDATE_URL = "https://be.4mmo.top/api/updates"
PRODUCT_SLUG = "npb-podcast-writer"
REQUEST_TIMEOUT = 10


def _get_update_url() -> str:
    url = get_setting("update_server_url")
    return url if url else DEFAULT_UPDATE_URL


def check_for_update() -> dict | None:
    """Check if a new version is available.
    Returns update info dict or None if up to date.
    """
    try:
        url = f"{_get_update_url()}/{PRODUCT_SLUG}/latest"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        data = resp.json()
        remote_version = data.get("version", "")

        if _is_newer(remote_version, APP_VERSION):
            return {
                "version": remote_version,
                "download_url": data.get("download_url", ""),
                "changelog": data.get("changelog", ""),
                "required": data.get("required", False),
            }
        return None

    except Exception:
        return None


def download_and_install(download_url: str) -> bool:
    """Download new .exe and launch installer."""
    try:
        resp = requests.get(download_url, stream=True, timeout=120)
        if resp.status_code != 200:
            return False

        tmp_dir = tempfile.mkdtemp()
        exe_path = os.path.join(tmp_dir, "npb-podcast-update.exe")

        with open(exe_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Launch the new installer and exit current app
        subprocess.Popen([exe_path])
        return True

    except Exception:
        return False


def _is_newer(remote: str, local: str) -> bool:
    """Compare semver strings. Returns True if remote > local."""
    try:
        r_parts = [int(x) for x in remote.split(".")]
        l_parts = [int(x) for x in local.split(".")]
        return r_parts > l_parts
    except (ValueError, AttributeError):
        return False


def get_current_version() -> str:
    return APP_VERSION
