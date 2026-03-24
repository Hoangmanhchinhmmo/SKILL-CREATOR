"""
License Service — Activate, verify, cache management.
Calls license-manager backend API.
"""

import json
import datetime
import requests

from db.models import (
    get_license_cache, save_license_cache, update_license_verified, clear_license_cache,
    get_setting, set_setting,
)
from services.machine_id import get_machine_code
from services.crypto import encrypt, decrypt

DEFAULT_SERVER_URL = "https://license.yourdomain.com/api"
GRACE_PERIOD_HOURS = 24
VERIFY_INTERVAL_HOURS = 4
REQUEST_TIMEOUT = 15


def _get_server_url() -> str:
    """Get license server URL from settings or default."""
    url = get_setting("license_server_url")
    return url if url else DEFAULT_SERVER_URL


def activate(license_key: str) -> dict:
    """Activate a license on this machine.
    Returns: {"success": bool, "message": str, "data": dict}
    """
    machine_code = get_machine_code()
    server_url = _get_server_url()

    try:
        resp = requests.post(
            f"{server_url}/licenses/activate",
            json={
                "licenseKey": license_key,
                "machineCode": machine_code,
                "deviceName": "NPB Podcast Writer",
                "osInfo": "Windows",
            },
            timeout=REQUEST_TIMEOUT,
        )

        body = resp.json()

        if resp.status_code == 200 and body.get("success"):
            data = body.get("data", {})
            product = data.get("product", {}).get("name", "")
            plan = data.get("plan", {}).get("name", "")
            expires_at = data.get("expiresAt", "")

            # Save encrypted to SQLite
            token_data = encrypt(json.dumps(data), machine_code)
            save_license_cache(
                license_key=license_key,
                machine_code=machine_code,
                status="active",
                product=product,
                plan=plan,
                expires_at=expires_at,
                token_data=token_data,
            )
            return {"success": True, "message": "Kích hoạt thành công!", "data": data}
        else:
            msg = body.get("message", "Kích hoạt thất bại")
            return {"success": False, "message": msg, "data": {}}

    except requests.ConnectionError:
        return {"success": False, "message": "Không thể kết nối đến server", "data": {}}
    except requests.Timeout:
        return {"success": False, "message": "Server không phản hồi (timeout)", "data": {}}
    except Exception as e:
        return {"success": False, "message": f"Lỗi: {str(e)}", "data": {}}


def verify() -> dict:
    """Verify current license with server.
    Returns: {"valid": bool, "grace": bool, "message": str}
    """
    cache = get_license_cache()
    if not cache:
        return {"valid": False, "grace": False, "message": "Chưa kích hoạt"}

    machine_code = get_machine_code()
    if cache["machine_code"] != machine_code:
        return {"valid": False, "grace": False, "message": "Machine code không khớp"}

    server_url = _get_server_url()

    try:
        resp = requests.post(
            f"{server_url}/licenses/verify",
            json={
                "licenseKey": cache["license_key"],
                "machineCode": machine_code,
                "productSlug": "npb-podcast-writer",
            },
            timeout=REQUEST_TIMEOUT,
        )

        body = resp.json()
        data = body.get("data", body)

        if data.get("valid"):
            update_license_verified()
            grace = data.get("graceMode", False)
            return {"valid": True, "grace": grace, "message": "License hợp lệ"}
        else:
            reason = data.get("reason", "License không hợp lệ")
            return {"valid": False, "grace": False, "message": reason}

    except (requests.ConnectionError, requests.Timeout):
        # Offline — check grace period
        return _check_offline_grace(cache)
    except Exception as e:
        return _check_offline_grace(cache)


def _check_offline_grace(cache: dict) -> dict:
    """Check if we're within the offline grace period."""
    verified_at = cache.get("verified_at")
    if not verified_at:
        return {"valid": False, "grace": False, "message": "Cần kết nối internet để xác minh"}

    try:
        last_verified = datetime.datetime.fromisoformat(verified_at)
        elapsed = datetime.datetime.now() - last_verified
        if elapsed.total_seconds() < GRACE_PERIOD_HOURS * 3600:
            remaining = GRACE_PERIOD_HOURS - (elapsed.total_seconds() / 3600)
            return {
                "valid": True,
                "grace": True,
                "message": f"Offline mode — còn {remaining:.0f}h grace",
            }
    except (ValueError, TypeError):
        pass

    return {"valid": False, "grace": False, "message": "Hết thời gian grace (24h). Cần kết nối internet."}


def check_on_startup() -> dict:
    """Check license on app startup.
    Returns: {"valid": bool, "grace": bool, "message": str, "needs_activation": bool}
    """
    cache = get_license_cache()
    if not cache:
        return {"valid": False, "grace": False, "message": "", "needs_activation": True}

    # Check if machine code matches
    machine_code = get_machine_code()
    if cache["machine_code"] != machine_code:
        clear_license_cache()
        return {"valid": False, "grace": False, "message": "Máy khác, cần kích hoạt lại", "needs_activation": True}

    # Check if verified recently (< 24h)
    verified_at = cache.get("verified_at")
    if verified_at:
        try:
            last = datetime.datetime.fromisoformat(verified_at)
            elapsed_hours = (datetime.datetime.now() - last).total_seconds() / 3600
            if elapsed_hours < VERIFY_INTERVAL_HOURS:
                # Recently verified, skip network call
                return {"valid": True, "grace": False, "message": "OK", "needs_activation": False}
        except (ValueError, TypeError):
            pass

    # Need to verify with server
    result = verify()
    result["needs_activation"] = not result["valid"] and not result["grace"]
    return result


def deactivate() -> dict:
    """Deactivate license on this machine."""
    cache = get_license_cache()
    if not cache:
        return {"success": True, "message": "Không có license để hủy"}

    machine_code = get_machine_code()
    server_url = _get_server_url()

    try:
        requests.post(
            f"{server_url}/licenses/deactivate",
            json={
                "licenseKey": cache["license_key"],
                "machineCode": machine_code,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except Exception:
        pass  # Best effort — clear local cache regardless

    clear_license_cache()
    return {"success": True, "message": "Đã hủy kích hoạt"}


def get_license_info() -> dict | None:
    """Get license info for display."""
    cache = get_license_cache()
    if not cache:
        return None

    return {
        "license_key": cache["license_key"],
        "status": cache["status"],
        "product": cache.get("product", ""),
        "plan": cache.get("plan", ""),
        "expires_at": cache.get("expires_at", ""),
        "verified_at": cache.get("verified_at", ""),
    }
