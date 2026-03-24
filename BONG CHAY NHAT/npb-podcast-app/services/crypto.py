"""
Encrypt/Decrypt using machineCode as key.
Uses Fernet (AES-128-CBC) from cryptography library.
"""

import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken


def _derive_key(machine_code: str) -> bytes:
    """Derive a Fernet-compatible key from machineCode string."""
    digest = hashlib.sha256(machine_code.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(data: str, machine_code: str) -> str:
    """Encrypt a string using machineCode-derived key."""
    key = _derive_key(machine_code)
    return Fernet(key).encrypt(data.encode()).decode()


def decrypt(data: str, machine_code: str) -> str:
    """Decrypt a string using machineCode-derived key.
    Returns empty string if decryption fails (wrong machine).
    """
    try:
        key = _derive_key(machine_code)
        return Fernet(key).decrypt(data.encode()).decode()
    except (InvalidToken, Exception):
        return ""
