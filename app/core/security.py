import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import platform
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("tmusic.security")

# Version tag for ciphertext payload format
CIPHERTEXT_VERSION_V1 = b"\x01"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _setup_windows_dpapi():
    """Setup explicit 64-bit argtypes and restype for Windows DPAPI to prevent pointer truncation."""
    if platform.system() != "Windows":
        return None, None

    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL

        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL

        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        return crypt32, kernel32
    except Exception as exc:
        logger.warning("Failed to configure 64-bit Windows DPAPI types: %s", exc)
        return None, None


_CRYPT32, _KERNEL32 = _setup_windows_dpapi()


def _protect_bytes_windows(data: bytes) -> bytes:
    """Protect master key using 64-bit safe Windows DPAPI (CryptProtectData)."""
    if not _CRYPT32 or not _KERNEL32:
        return data

    try:
        in_bytes = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        in_blob = DATA_BLOB(len(data), ctypes.cast(in_bytes, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        if _CRYPT32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        ):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            _KERNEL32.LocalFree(out_blob.pbData)
            return result
    except Exception as exc:
        logger.warning("Windows DPAPI protect failed, using raw key: %s", exc)
    return data


def _unprotect_bytes_windows(protected_data: bytes) -> bytes:
    """Unprotect master key using 64-bit safe Windows DPAPI (CryptUnprotectData)."""
    if not _CRYPT32 or not _KERNEL32:
        return protected_data

    try:
        in_bytes = (ctypes.c_ubyte * len(protected_data)).from_buffer_copy(protected_data)
        in_blob = DATA_BLOB(len(protected_data), ctypes.cast(in_bytes, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        if _CRYPT32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
        ):
            result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            _KERNEL32.LocalFree(out_blob.pbData)
            return result
    except Exception as exc:
        logger.warning("Windows DPAPI unprotect failed: %s", exc)
    return protected_data


class CryptoManager:
    """Manages authenticated AES-256-GCM encryption with 64-bit safe OS-protected key storage."""

    def __init__(self, key_storage_dir: Path) -> None:
        self._key_storage_dir = key_storage_dir
        self._key_file = key_storage_dir / ".master.key"
        self._aesgcm = AESGCM(self._get_or_create_master_key())

    def _get_or_create_master_key(self) -> bytes:
        self._key_storage_dir.mkdir(parents=True, exist_ok=True)
        is_windows = platform.system() == "Windows"

        if self._key_file.exists():
            try:
                raw_bytes = self._key_file.read_bytes()
                key = _unprotect_bytes_windows(raw_bytes) if is_windows else raw_bytes
                if len(key) == 32:
                    return key
            except Exception as exc:
                logger.error("Failed to read master key: %s", exc)

        # Generate a stable 256-bit (32 bytes) master key
        logger.info("Generating new 256-bit cryptographic master key...")
        new_key = AESGCM.generate_key(bit_length=256)
        protected = _protect_bytes_windows(new_key) if is_windows else new_key

        try:
            self._key_file.write_bytes(protected)
        except Exception as exc:
            logger.error("Failed to persist master key to disk: %s", exc)

        return new_key

    def encrypt(self, plaintext: bytes | str) -> bytes:
        """Encrypt payload using AES-256-GCM."""
        data_bytes = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        nonce = os.urandom(12)  # Standard 96-bit nonce for GCM
        ciphertext = self._aesgcm.encrypt(nonce, data_bytes, associated_data=CIPHERTEXT_VERSION_V1)
        # Format: [Version 1B][Nonce 12B][Ciphertext + 16B Auth Tag]
        return CIPHERTEXT_VERSION_V1 + nonce + ciphertext

    def decrypt(self, encrypted_payload: bytes) -> bytes:
        """Decrypt and authenticate payload using AES-256-GCM."""
        if len(encrypted_payload) < 1 + 12 + 16:
            raise ValueError("Invalid encrypted payload size")

        version = encrypted_payload[:1]
        if version != CIPHERTEXT_VERSION_V1:
            raise ValueError(f"Unsupported ciphertext version: {version!r}")

        nonce = encrypted_payload[1:13]
        ciphertext = encrypted_payload[13:]

        return self._aesgcm.decrypt(nonce, ciphertext, associated_data=CIPHERTEXT_VERSION_V1)

    def save_encrypted_json(self, file_path: Path, data: dict[str, Any]) -> None:
        """Serialize dictionary to securely encrypted binary file."""
        json_str = json.dumps(data, ensure_ascii=False)
        encrypted_bytes = self.encrypt(json_str)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(encrypted_bytes)

    def load_encrypted_json(self, file_path: Path) -> dict[str, Any]:
        """Decrypt file and parse into dictionary. Returns empty dict if missing or reset on corruption."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            return {}

        try:
            encrypted_bytes = file_path.read_bytes()
            decrypted_bytes = self.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as exc:
            logger.warning("Could not decrypt JSON file %s: %s (resetting stale state)", file_path, exc)
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
            return {}