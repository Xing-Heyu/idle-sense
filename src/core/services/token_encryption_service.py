"""
代币加密存储基础设施

实现:
- AES-256-GCM 加密/解密
- PBKDF2-HMAC-SHA256 密钥派生
- HMAC-SHA256 数据完整性验证
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any, Optional

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


class EncryptionError(Exception):
    """加密错误"""
    pass


class DecryptionError(Exception):
    """解密错误"""
    pass


class IntegrityError(Exception):
    """数据完整性错误"""
    pass


@dataclass
class EncryptedData:
    """加密数据结构"""
    ciphertext: bytes
    nonce: bytes
    salt: bytes
    hmac: bytes
    version: str = "1.0"

    def to_dict(self) -> dict[str, str]:
        """转换为字典（用于存储）"""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "salt": base64.b64encode(self.salt).decode(),
            "hmac": base64.b64encode(self.hmac).decode(),
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "EncryptedData":
        """从字典创建"""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            nonce=base64.b64decode(data["nonce"]),
            salt=base64.b64decode(data["salt"]),
            hmac=base64.b64decode(data["hmac"]),
            version=data.get("version", "1.0")
        )


class TokenEncryption:
    """代币加密服务"""

    # 加密参数
    KEY_SIZE = 32  # AES-256
    NONCE_SIZE = 12  # GCM 推荐 nonce 大小
    SALT_SIZE = 16
    PBKDF2_ITERATIONS = 100000
    HMAC_KEY_SIZE = 32

    def __init__(
        self,
        main_password: Optional[str] = None,
        key_file: Optional[str] = None,
        salt_file: Optional[str] = None
    ):
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography 库未安装，请运行: pip install cryptography"
            )

        self._main_password = main_password
        self._key_file = key_file
        self._salt_file = salt_file
        self._encryption_key: Optional[bytes] = None
        self._hmac_key: Optional[bytes] = None

        if main_password:
            self._derive_keys_from_password(main_password)
        elif key_file:
            self._load_keys_from_file(key_file)

    def set_main_password(self, password: str) -> None:
        """设置主密码并派生密钥"""
        self._main_password = password
        self._derive_keys_from_password(password)

    def _derive_keys_from_password(self, password: str) -> None:
        if self._salt_file and os.path.exists(self._salt_file):
            with open(self._salt_file, "r") as f:
                salt = base64.b64decode(f.read().strip())
        else:
            salt = secrets.token_bytes(self.SALT_SIZE)
            if self._salt_file:
                os.makedirs(os.path.dirname(self._salt_file), exist_ok=True)
                with open(self._salt_file, "w") as f:
                    f.write(base64.b64encode(salt).decode())

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE + self.HMAC_KEY_SIZE,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS
        )

        key_material = kdf.derive(password.encode())
        self._encryption_key = key_material[:self.KEY_SIZE]
        self._hmac_key = key_material[self.KEY_SIZE:]
        self._last_salt = salt

    def save_keys_to_file(self, file_path: str, protect_with_password: bool = True) -> None:
        """
        保存密钥到文件

        Args:
            file_path: 密钥文件路径
            protect_with_password: 是否用密码保护
        """
        if self._encryption_key is None or self._hmac_key is None:
            raise EncryptionError("密钥未设置")

        key_data = {
            "encryption_key": base64.b64encode(self._encryption_key).decode(),
            "hmac_key": base64.b64encode(self._hmac_key).decode(),
            "salt": base64.b64encode(self._last_salt).decode() if hasattr(self, '_last_salt') else None
        }

        key_json = json.dumps(key_data)

        if protect_with_password and self._main_password:
            temp_enc = TokenEncryption(self._main_password)
            encrypted = temp_enc._encrypt_raw(key_json.encode())
            key_json = json.dumps(encrypted.to_dict())

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(key_json)

    def _load_keys_from_file(self, file_path: str, password: Optional[str] = None) -> None:
        """从文件加载密钥"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"密钥文件不存在: {file_path}")

        with open(file_path) as f:
            key_json = f.read()

        key_data = json.loads(key_json)

        if "version" in key_data and "ciphertext" in key_data:
            if not password and not self._main_password:
                raise EncryptionError("需要密码才能解密密钥文件")

            pwd = password or self._main_password
            temp_enc = TokenEncryption(pwd)
            encrypted_data = EncryptedData.from_dict(key_data)
            decrypted = temp_enc._decrypt_raw(encrypted_data)
            key_data = json.loads(decrypted.decode())

        self._encryption_key = base64.b64decode(key_data["encryption_key"])
        self._hmac_key = base64.b64decode(key_data["hmac_key"])

        if key_data.get("salt"):
            self._last_salt = base64.b64decode(key_data["salt"])

    def _compute_hmac(self, data: bytes) -> bytes:
        """计算HMAC"""
        if self._hmac_key is None:
            raise EncryptionError("HMAC密钥未设置")

        return hmac.new(
            self._hmac_key,
            data,
            hashlib.sha256
        ).digest()

    def _verify_hmac(self, data: bytes, hmac_value: bytes) -> bool:
        """验证HMAC"""
        expected_hmac = self._compute_hmac(data)
        return hmac.compare_digest(expected_hmac, hmac_value)

    def _encrypt_raw(self, plaintext: bytes) -> EncryptedData:
        """
        原始加密（内部使用）

        Args:
            plaintext: 明文数据

        Returns:
            加密数据
        """
        if self._encryption_key is None:
            raise EncryptionError("加密密钥未设置")

        nonce = secrets.token_bytes(self.NONCE_SIZE)
        salt = secrets.token_bytes(self.SALT_SIZE)

        aesgcm = AESGCM(self._encryption_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=salt)

        hmac_value = self._compute_hmac(ciphertext + nonce + salt)

        return EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            salt=salt,
            hmac=hmac_value
        )

    def _decrypt_raw(self, encrypted_data: EncryptedData) -> bytes:
        """
        原始解密（内部使用）

        Args:
            encrypted_data: 加密数据

        Returns:
            明文数据
        """
        if self._encryption_key is None:
            raise DecryptionError("加密密钥未设置")

        if not self._verify_hmac(
            encrypted_data.ciphertext + encrypted_data.nonce + encrypted_data.salt,
            encrypted_data.hmac
        ):
            raise IntegrityError("数据完整性验证失败")

        try:
            aesgcm = AESGCM(self._encryption_key)
            plaintext = aesgcm.decrypt(
                encrypted_data.nonce,
                encrypted_data.ciphertext,
                associated_data=encrypted_data.salt
            )
            return plaintext
        except Exception as e:
            raise DecryptionError(f"解密失败: {str(e)}") from e

    def encrypt(self, data: dict[str, Any]) -> EncryptedData:
        """
        加密字典数据

        Args:
            data: 要加密的数据字典

        Returns:
            加密数据
        """
        plaintext = json.dumps(data).encode()
        return self._encrypt_raw(plaintext)

    def decrypt(self, encrypted_data: EncryptedData) -> dict[str, Any]:
        """
        解密为字典数据

        Args:
            encrypted_data: 加密数据

        Returns:
            解密后的数据字典
        """
        plaintext = self._decrypt_raw(encrypted_data)
        return json.loads(plaintext.decode())

    def encrypt_to_string(self, data: dict[str, Any]) -> str:
        """加密为字符串（用于存储）"""
        encrypted = self.encrypt(data)
        return json.dumps(encrypted.to_dict())

    def decrypt_from_string(self, encrypted_str: str) -> dict[str, Any]:
        """从字符串解密"""
        data_dict = json.loads(encrypted_str)
        encrypted_data = EncryptedData.from_dict(data_dict)
        return self.decrypt(encrypted_data)

    def rotate_keys(
        self,
        new_password: Optional[str] = None,
        new_key_file: Optional[str] = None
    ) -> None:
        """
        轮换密钥

        注意：此操作需要重新加密所有现有数据
        """

        if new_password:
            self._derive_keys_from_password(new_password)
            self._main_password = new_password
        elif new_key_file:
            raise NotImplementedError("从文件轮换密钥需要特殊处理")
        else:
            raise ValueError("必须提供新密码或新密钥文件")

    def clear_keys(self) -> None:
        """清除内存中的密钥"""
        self._encryption_key = None
        self._hmac_key = None
        self._main_password = None


__all__ = [
    "TokenEncryption",
    "EncryptedData",
    "EncryptionError",
    "DecryptionError",
    "IntegrityError"
]
