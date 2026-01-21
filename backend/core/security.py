import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class SecurityCore:
    """
    Encryption helper for secrets at rest.
    Uses Fernet (AES128 + HMAC) with key provided via env `APEX_KMS_KEY`.
    """

    def __init__(self):
        self.logger = logging.getLogger("Apex.SecurityCore")
        key_b64 = os.getenv("APEX_KMS_KEY")
        if not key_b64:
            raise ValueError("APEX_KMS_KEY environment variable is not set.")

        try:
            # Accept either a raw Fernet key or urlsafe base64 string
            key_bytes = key_b64.encode()
            # If the key is not a valid Fernet length, try base64-decoding
            try:
                base64.urlsafe_b64decode(key_bytes)
                self.fernet = Fernet(key_bytes)
            except Exception:
                decoded = base64.urlsafe_b64decode(key_bytes)
                self.fernet = Fernet(base64.urlsafe_b64encode(decoded))
        except Exception as e:
            raise ValueError(f"Invalid APEX_KMS_KEY: {e}")

    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            raise ValueError("Cannot encrypt None")
        token = self.fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        if token is None:
            raise ValueError("Cannot decrypt None")
        try:
            plaintext = self.fernet.decrypt(token.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken as e:
            self.logger.error("Failed to decrypt secret: invalid token")
            raise e


# Singleton
security_core = SecurityCore()
