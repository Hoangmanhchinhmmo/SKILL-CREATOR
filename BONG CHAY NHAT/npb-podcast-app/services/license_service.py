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

DEFAULT_SERVER_URL = "https://be.4mmo.top/api"
GRACE_PERIOD_HOURS = 24
VERIFY_INTERVAL_HOURS = 4
REQUEST_TIMEOUT = 15


def _get_server_url() -> str:
    """Get license server URL from settings or default."""
    url = get_setting("license_server_url")
    if url and "yourdomain" not in url:
        return url
    return DEFAULT_SERVER_URL


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
            # Response may nest under data.license or directly in data
            lic_data = data.get("license", data)
            product = lic_data.get("product", {}).get("name", "") if isinstance(lic_data.get("product"), dict) else ""
            plan = lic_data.get("plan", {}).get("name", "") if isinstance(lic_data.get("plan"), dict) else ""
            expires_at = lic_data.get("expiresAt", "")

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
            grace = data.get("graceMode", False)
            if grace:
                # Grace mode = device was reset/deactivated — treat as invalid, require re-activate
                clear_license_cache()
                return {"valid": False, "grace": False, "message": "Device đã bị reset. Cần kích hoạt lại."}
            update_license_verified()
            return {"valid": True, "grace": False, "message": "License hợp lệ"}
        else:
            reason = data.get("reason", "License không hợp lệ")
            # License revoked/suspended/expired on server → clear local cache
            if any(kw in reason.lower() for kw in ["revoked", "suspended", "not activated", "not found"]):
                clear_license_cache()
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
    ALWAYS verifies with server. Only falls back to grace if offline.
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

    # ALWAYS verify with server on startup — catch revoke/reset immediately
    result = verify()

    # If server says invalid and not in grace → clear cache, force re-activation
    if not result["valid"] and not result["grace"]:
        clear_license_cache()
        result["needs_activation"] = True
    else:
        result["needs_activation"] = False

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


def get_days_remaining() -> dict:
    """Calculate remaining days for the license.
    Returns: {"days": int, "expired": bool, "expires_at": str, "total_estimate": int}
    """
    cache = get_license_cache()
    if not cache or not cache.get("expires_at"):
        return {"days": 0, "expired": True, "expires_at": "", "total_estimate": 0}

    try:
        expires_str = cache["expires_at"]
        # Handle both ISO format and date-only
        if "T" in expires_str:
            expires_dt = datetime.datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
        else:
            expires_dt = datetime.datetime.strptime(expires_str, "%Y-%m-%d")
            now = datetime.datetime.now()

        delta = expires_dt - now
        days = delta.days

        # Estimate total days (use 365 as default, or actual remaining if larger)
        total_estimate = max(365, abs(days) + 30)

        return {
            "days": days,
            "expired": days < 0,
            "expires_at": expires_str,
            "total_estimate": total_estimate,
        }
    except (ValueError, TypeError):
        return {"days": 0, "expired": True, "expires_at": cache.get("expires_at", ""), "total_estimate": 0}
