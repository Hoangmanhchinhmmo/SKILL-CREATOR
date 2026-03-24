"""
Admin License Service — Manage licenses via license-manager Admin API.
Requires admin JWT token from POST /api/auth/login.
"""

import requests
from db.models import get_setting, set_setting
from services.machine_id import get_machine_code
from services.crypto import encrypt, decrypt

REQUEST_TIMEOUT = 15

ADMIN_TOKEN_KEY = "admin_jwt_token"
ADMIN_EMAIL_KEY = "admin_email"


def _get_server_url() -> str:
    url = get_setting("license_server_url")
    if url and "yourdomain" not in url:
        return url
    return "https://be.4mmo.top/api"


def _get_token() -> str | None:
    """Get stored admin JWT token (decrypted)."""
    encrypted = get_setting(ADMIN_TOKEN_KEY)
    if not encrypted:
        return None
    mc = get_machine_code()
    return decrypt(encrypted, mc)


def _save_token(token: str, email: str):
    """Save admin JWT token (encrypted)."""
    mc = get_machine_code()
    set_setting(ADMIN_TOKEN_KEY, encrypt(token, mc), encrypted=True)
    set_setting(ADMIN_EMAIL_KEY, email)


def _headers() -> dict:
    token = _get_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def is_logged_in() -> bool:
    return _get_token() is not None


def get_admin_email() -> str:
    return get_setting(ADMIN_EMAIL_KEY) or ""


def login(email: str, password: str) -> dict:
    """Login as admin. Returns {"success": bool, "message": str}."""
    url = _get_server_url()
    try:
        resp = requests.post(
            f"{url}/auth/login",
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        body = resp.json()
        if resp.status_code == 200 and body.get("success"):
            data = body.get("data", body)
            token = data.get("token") or data.get("accessToken") or ""
            user = data.get("user", {})
            role = user.get("role", "")
            if role != "ADMIN":
                return {"success": False, "message": "Tài khoản không có quyền Admin"}
            _save_token(token, email)
            return {"success": True, "message": "Đăng nhập thành công"}
        else:
            return {"success": False, "message": body.get("message", "Đăng nhập thất bại")}
    except requests.ConnectionError:
        return {"success": False, "message": "Không thể kết nối server"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def logout():
    """Clear stored admin token."""
    set_setting(ADMIN_TOKEN_KEY, "", encrypted=False)
    set_setting(ADMIN_EMAIL_KEY, "")


def _api_call(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> dict:
    """Generic API call with auto-retry on 401."""
    url = f"{_get_server_url()}{endpoint}"
    try:
        resp = requests.request(
            method, url, headers=_headers(),
            json=json_data, params=params, timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 401:
            return {"success": False, "message": "Token hết hạn. Đăng nhập lại.", "auth_error": True}
        body = resp.json()
        if resp.status_code >= 400:
            return {"success": False, "message": body.get("message", f"Error {resp.status_code}")}
        return {"success": True, "data": body.get("data", body)}
    except requests.ConnectionError:
        return {"success": False, "message": "Không thể kết nối server"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_licenses(page: int = 1, limit: int = 20, status: str = "", search: str = "") -> dict:
    """GET /api/licenses/admin/all — list all licenses."""
    params = {"page": page, "limit": limit}
    if status:
        params["status"] = status
    if search:
        params["search"] = search
    return _api_call("GET", "/licenses/admin/all", params=params)


def get_license_detail(license_id: str) -> dict:
    """GET /api/licenses/admin/:id"""
    return _api_call("GET", f"/licenses/admin/{license_id}")


def extend_license(license_id: str, days: int) -> dict:
    """PUT /api/licenses/admin/:id/extend"""
    return _api_call("PUT", f"/licenses/admin/{license_id}/extend", json_data={"days": days})


def revoke_license(license_id: str, reason: str = "") -> dict:
    """PUT /api/licenses/admin/:id/revoke"""
    return _api_call("PUT", f"/licenses/admin/{license_id}/revoke", json_data={"reason": reason})


def suspend_license(license_id: str, reason: str = "") -> dict:
    """PUT /api/licenses/admin/:id/suspend"""
    return _api_call("PUT", f"/licenses/admin/{license_id}/suspend", json_data={"reason": reason})


def reset_devices(license_id: str, reason: str = "") -> dict:
    """PUT /api/licenses/admin/:id/reset-devices"""
    return _api_call("PUT", f"/licenses/admin/{license_id}/reset-devices", json_data={"reason": reason})
