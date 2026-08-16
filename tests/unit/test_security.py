import pytest
from pathlib import Path
from app.core.security import CryptoManager


def test_encryption_decryption_roundtrip(tmp_path: Path) -> None:
    """Verify that plaintext encrypts and decrypts accurately with AES-256-GCM."""
    crypto = CryptoManager(tmp_path)
    secret_text = "TMusic-Secret-Telegram-Proxy-Password-123456"

    # Encrypt
    encrypted_bytes = crypto.encrypt(secret_text)
    assert isinstance(encrypted_bytes, bytes)
    assert secret_text.encode() not in encrypted_bytes  # Ciphertext must not contain plaintext

    # Decrypt
    decrypted_bytes = crypto.decrypt(encrypted_bytes)
    assert decrypted_bytes.decode("utf-8") == secret_text


def test_corrupted_payload_fails_gracefully(tmp_path: Path) -> None:
    """Verify corrupted ciphertext raises ValueError and does not decrypt."""
    crypto = CryptoManager(tmp_path)
    secret_text = "Important Payload"
    encrypted_bytes = bytearray(crypto.encrypt(secret_text))

    # Tamper with the last byte (auth tag)
    encrypted_bytes[-1] ^= 0xFF

    with pytest.raises(Exception):
        crypto.decrypt(bytes(encrypted_bytes))


def test_save_and_load_encrypted_json(tmp_path: Path) -> None:
    """Verify dictionary serialization and decryption from disk."""
    crypto = CryptoManager(tmp_path)
    json_file = tmp_path / "test_secure.enc"

    data = {
        "proxy_host": "127.0.0.1",
        "proxy_port": 10808,
        "volume": 95,
        "is_active": True,
    }

    crypto.save_encrypted_json(json_file, data)
    assert json_file.exists()

    loaded_data = crypto.load_encrypted_json(json_file)
    assert loaded_data == data