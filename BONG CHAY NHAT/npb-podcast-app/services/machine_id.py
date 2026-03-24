"""
Machine ID — Generate unique machineCode from CPU + Motherboard.
Windows compatible (Win10 + Win11). Uses PowerShell CIM, fallback to wmic.
"""

import subprocess
import hashlib
import sys

# Hide CMD windows on Windows GUI apps
_STARTUP_INFO = None
_CREATION_FLAGS = 0
if sys.platform == "win32":
    _STARTUP_INFO = subprocess.STARTUPINFO()
    _STARTUP_INFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUP_INFO.wShowWindow = 0  # SW_HIDE
    _CREATION_FLAGS = subprocess.CREATE_NO_WINDOW

# Cache machine code — hardware IDs don't change during a session
_cached_machine_code: str | None = None


def _run_powershell(query: str) -> str:
    """Run a PowerShell Get-CimInstance query. Returns first line only."""
    try:
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", query],
            stderr=subprocess.DEVNULL,
            timeout=10,
            startupinfo=_STARTUP_INFO,
            creationflags=_CREATION_FLAGS,
        ).decode("utf-8", errors="replace").strip()
        # Take first line only (multi-socket CPUs return multiple lines)
        first_line = output.split("\n")[0].strip() if output else ""
        return first_line if first_line else "UNKNOWN"
    except (subprocess.SubprocessError, OSError):
        return ""


def _run_wmic(query: str) -> str:
    """Fallback: Run a wmic command (deprecated on Win11 but still works on Win10)."""
    try:
        output = subprocess.check_output(
            query.split(),
            stderr=subprocess.DEVNULL,
            timeout=10,
            startupinfo=_STARTUP_INFO,
            creationflags=_CREATION_FLAGS,
        ).decode("utf-8", errors="replace")
        lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
        if len(lines) >= 2:
            return lines[1]
        return lines[0] if lines else "UNKNOWN"
    except (subprocess.SubprocessError, OSError):
        return "UNKNOWN"


def _get_value(ps_query: str, wmic_query: str) -> str:
    """Try PowerShell first, fallback to wmic."""
    result = _run_powershell(ps_query)
    if result and result != "UNKNOWN":
        return result
    return _run_wmic(wmic_query)


def get_cpu_id() -> str:
    return _get_value(
        "(Get-CimInstance Win32_Processor).ProcessorId",
        "wmic cpu get ProcessorId",
    )


def get_board_serial() -> str:
    return _get_value(
        "(Get-CimInstance Win32_BaseBoard).SerialNumber",
        "wmic baseboard get SerialNumber",
    )


def get_machine_code() -> str:
    """Generate machineCode: SHA256(cpuId | boardSerial). Cached after first call."""
    global _cached_machine_code
    if _cached_machine_code is None:
        cpu = get_cpu_id()
        board = get_board_serial()
        raw = f"{cpu}|{board}"
        _cached_machine_code = hashlib.sha256(raw.encode()).hexdigest()
    return _cached_machine_code


def get_hardware_info() -> dict:
    """Get human-readable hardware info for License tab display."""
    cpu_name = _get_value(
        "(Get-CimInstance Win32_Processor).Name",
        "wmic cpu get Name",
    )
    board_product = _get_value(
        "(Get-CimInstance Win32_BaseBoard).Product",
        "wmic baseboard get Product",
    )
    board_mfr = _get_value(
        "(Get-CimInstance Win32_BaseBoard).Manufacturer",
        "wmic baseboard get Manufacturer",
    )
    return {
        "cpu": cpu_name,
        "mainboard": f"{board_mfr} {board_product}".strip(),
        "machine_code": get_machine_code(),
    }
