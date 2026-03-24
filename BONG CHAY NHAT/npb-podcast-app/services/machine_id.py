"""
Machine ID — Generate unique machineCode from CPU + Motherboard.
Windows only (uses wmic).
"""

import subprocess
import hashlib


def _run_wmic(query: str) -> str:
    """Run a wmic command and return the first data line."""
    try:
        output = subprocess.check_output(
            query, shell=True, stderr=subprocess.DEVNULL, timeout=10,
        ).decode("utf-8", errors="replace")
        lines = [l.strip() for l in output.strip().split("\n") if l.strip()]
        # First line is header, second is data
        if len(lines) >= 2:
            return lines[1]
        return lines[0] if lines else "UNKNOWN"
    except (subprocess.SubprocessError, OSError):
        return "UNKNOWN"


def get_cpu_id() -> str:
    """Get CPU ProcessorId."""
    return _run_wmic("wmic cpu get ProcessorId")


def get_board_serial() -> str:
    """Get Motherboard SerialNumber."""
    return _run_wmic("wmic baseboard get SerialNumber")


def get_machine_code() -> str:
    """Generate machineCode: SHA256(cpuId | boardSerial)."""
    cpu = get_cpu_id()
    board = get_board_serial()
    raw = f"{cpu}|{board}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_hardware_info() -> dict:
    """Get human-readable hardware info for License tab display."""
    cpu_name = _run_wmic("wmic cpu get Name")
    board_product = _run_wmic("wmic baseboard get Product")
    board_manufacturer = _run_wmic("wmic baseboard get Manufacturer")

    return {
        "cpu": cpu_name,
        "mainboard": f"{board_manufacturer} {board_product}".strip(),
        "machine_code": get_machine_code(),
    }
