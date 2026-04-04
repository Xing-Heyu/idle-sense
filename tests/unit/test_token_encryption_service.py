"""
代币加密服务单元测试

测试覆盖:
- AES-256-GCM 加密/解密
- PBKDF2 密钥派生
- HMAC 签名验证
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.core.services.token_encryption_service import (
    DecryptionError,
    EncryptedData,
    EncryptionError,
    IntegrityError,
    TokenEncryption,
)


class TestEncryptedData(unittest.TestCase):
    """测试加密数据结构"""

    def test_encrypted_data_creation(self):
        encrypted = EncryptedData(
            ciphertext=b"ciphertext_data",
            nonce=b"nonce_12bytes",
            salt=b"salt_16bytes_",
            hmac=b"hmac_32bytes_signature_data"
        )

        self.assertEqual(encrypted.ciphertext, b"ciphertext_data")
        self.assertEqual(encrypted.nonce, b"nonce_12bytes")
        self.assertEqual(encrypted.salt, b"salt_16bytes_")
        self.assertEqual(encrypted.hmac, b"hmac_32bytes_signature_data")

    def test_encrypted_data_default_version(self):
        encrypted = EncryptedData(
            ciphertext=b"data",
            nonce=b"nonce",
            salt=b"salt",
            hmac=b"hmac"
        )

        self.assertEqual(encrypted.version, "1.0")

    def test_encrypted_data_to_dict(self):
        encrypted = EncryptedData(
            ciphertext=b"ciphertext",
            nonce=b"nonce123456",
            salt=b"salt123456789012",
            hmac=b"hmac12345678901234567890123456",
            version="1.0"
        )

        data = encrypted.to_dict()

        self.assertIn("ciphertext", data)
        self.assertIn("nonce", data)
        self.assertIn("salt", data)
        self.assertIn("hmac", data)
        self.assertIn("version", data)

    def test_encrypted_data_from_dict(self):
        original = EncryptedData(
            ciphertext=b"test_ciphertext",
            nonce=b"test_nonce_12",
            salt=b"test_salt_16_by",
            hmac=b"test_hmac_32_bytes_signature"
        )

        data = original.to_dict()
        restored = EncryptedData.from_dict(data)

        self.assertEqual(restored.ciphertext, original.ciphertext)
        self.assertEqual(restored.nonce, original.nonce)
        self.assertEqual(restored.salt, original.salt)
        self.assertEqual(restored.hmac, original.hmac)

    def test_encrypted_data_roundtrip(self):
        original = EncryptedData(
            ciphertext=b"complex ciphertext with special chars: \x00\xff",
            nonce=b"nonce_12_b",
            salt=b"salt_16_bytes!",
            hmac=b"hmac_signature_32_bytes_here!!",
            version="2.0"
        )

        data = original.to_dict()
        restored = EncryptedData.from_dict(data)

        self.assertEqual(restored.ciphertext, original.ciphertext)
        self.assertEqual(restored.version, original.version)


class TestAES256GCMEncryption(unittest.TestCase):
    """测试 AES-256-GCM 加密/解密"""

    def setUp(self):
        self.password = "test_password_123"
        self.encryption = TokenEncryption(main_password=self.password)

    def test_encrypt_decrypt_basic(self):
        data = {"message": "Hello, World!", "value": 42}

        encrypted = self.encryption.encrypt(data)
        decrypted = self.encryption.decrypt(encrypted)

        self.assertEqual(decrypted["message"], "Hello, World!")
        self.assertEqual(decrypted["value"], 42)

    def test_encrypt_produces_different_ciphertext(self):
        data = {"message": "same message"}

        encrypted1 = self.encryption.encrypt(data)
        encrypted2 = self.encryption.encrypt(data)

        self.assertNotEqual(encrypted1.ciphertext, encrypted2.ciphertext)
        self.assertNotEqual(encrypted1.nonce, encrypted2.nonce)

    def test_encrypt_decrypt_complex_data(self):
        data = {
            "string": "test string",
            "integer": 12345,
            "float": 3.14159,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3, 4, 5],
            "nested": {
                "key1": "value1",
                "key2": {"nested_key": "nested_value"}
            }
        }

        encrypted = self.encryption.encrypt(data)
        decrypted = self.encryption.decrypt(encrypted)

        self.assertEqual(decrypted["string"], data["string"])
        self.assertEqual(decrypted["integer"], data["integer"])
        self.assertEqual(decrypted["float"], data["float"])
        self.assertEqual(decrypted["boolean"], data["boolean"])
        self.assertEqual(decrypted["array"], data["array"])
        self.assertEqual(decrypted["nested"]["key1"], data["nested"]["key1"])

    def test_encrypt_decrypt_empty_data(self):
        data = {}

        encrypted = self.encryption.encrypt(data)
        decrypted = self.encryption.decrypt(encrypted)

        self.assertEqual(decrypted, {})

    def test_encrypt_decrypt_string_methods(self):
        data = {"key": "value", "number": 123}

        encrypted_str = self.encryption.encrypt_to_string(data)
        decrypted = self.encryption.decrypt_from_string(encrypted_str)

        self.assertEqual(decrypted["key"], "value")
        self.assertEqual(decrypted["number"], 123)

    def test_encrypt_raw_basic(self):
        plaintext = b"raw bytes data"

        encrypted = self.encryption._encrypt_raw(plaintext)

        self.assertIsNotNone(encrypted.ciphertext)
        self.assertIsNotNone(encrypted.nonce)
        self.assertIsNotNone(encrypted.salt)
        self.assertIsNotNone(encrypted.hmac)
        self.assertEqual(len(encrypted.nonce), TokenEncryption.NONCE_SIZE)

    def test_decrypt_raw_basic(self):
        plaintext = b"raw bytes to encrypt and decrypt"

        encrypted = self.encryption._encrypt_raw(plaintext)
        decrypted = self.encryption._decrypt_raw(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_different_passwords_cannot_decrypt(self):
        data = {"secret": "confidential"}

        encrypted = self.encryption.encrypt(data)

        other_encryption = TokenEncryption(main_password="different_password")

        with self.assertRaises((DecryptionError, IntegrityError)):
            other_encryption.decrypt(encrypted)


class TestPBKDF2KeyDerivation(unittest.TestCase):
    """测试 PBKDF2 密钥派生"""

    def test_key_derivation_from_password(self):
        encryption = TokenEncryption(main_password="test_password")

        self.assertIsNotNone(encryption._encryption_key)
        self.assertIsNotNone(encryption._hmac_key)
        self.assertEqual(len(encryption._encryption_key), TokenEncryption.KEY_SIZE)
        self.assertEqual(len(encryption._hmac_key), TokenEncryption.HMAC_KEY_SIZE)

    def test_different_passwords_different_keys(self):
        encryption1 = TokenEncryption(main_password="password1")
        encryption2 = TokenEncryption(main_password="password2")

        self.assertNotEqual(encryption1._encryption_key, encryption2._encryption_key)
        self.assertNotEqual(encryption1._hmac_key, encryption2._hmac_key)

    def test_same_password_different_salt_different_keys(self):
        encryption1 = TokenEncryption(main_password="same_password")
        encryption2 = TokenEncryption(main_password="same_password")

        self.assertNotEqual(encryption1._encryption_key, encryption2._encryption_key)

    def test_set_main_password(self):
        encryption = TokenEncryption()
        encryption.set_main_password("new_password")

        self.assertIsNotNone(encryption._encryption_key)
        self.assertIsNotNone(encryption._hmac_key)

    def test_key_size_constants(self):
        self.assertEqual(TokenEncryption.KEY_SIZE, 32)
        self.assertEqual(TokenEncryption.NONCE_SIZE, 12)
        self.assertEqual(TokenEncryption.SALT_SIZE, 16)
        self.assertEqual(TokenEncryption.PBKDF2_ITERATIONS, 100000)


class TestHMACSignatureVerification(unittest.TestCase):
    """测试 HMAC 签名验证"""

    def setUp(self):
        self.password = "test_password"
        self.encryption = TokenEncryption(main_password=self.password)

    def test_hmac_computed_on_encrypt(self):
        data = {"test": "data"}

        encrypted = self.encryption.encrypt(data)

        self.assertIsNotNone(encrypted.hmac)
        self.assertEqual(len(encrypted.hmac), 32)

    def test_hmac_verification_success(self):
        data = {"test": "data"}

        encrypted = self.encryption.encrypt(data)

        combined_data = encrypted.ciphertext + encrypted.nonce + encrypted.salt
        self.assertTrue(self.encryption._verify_hmac(combined_data, encrypted.hmac))

    def test_hmac_verification_failure_tampered_data(self):
        data = {"test": "data"}

        encrypted = self.encryption.encrypt(data)
        encrypted.ciphertext = b"tampered_ciphertext"

        with self.assertRaises(IntegrityError):
            self.encryption.decrypt(encrypted)

    def test_hmac_verification_failure_tampered_hmac(self):
        data = {"test": "data"}

        encrypted = self.encryption.encrypt(data)
        encrypted.hmac = b"tampered_hmac_value_32_bytes_here"

        with self.assertRaises(IntegrityError):
            self.encryption.decrypt(encrypted)

    def test_compute_hmac(self):
        test_data = b"test data for hmac"
        hmac_value = self.encryption._compute_hmac(test_data)

        self.assertEqual(len(hmac_value), 32)

    def test_hmac_deterministic(self):
        test_data = b"same data"

        hmac1 = self.encryption._compute_hmac(test_data)
        hmac2 = self.encryption._compute_hmac(test_data)

        self.assertEqual(hmac1, hmac2)


class TestEncryptionErrors(unittest.TestCase):
    """测试加密错误处理"""

    def test_encryption_without_key(self):
        encryption = TokenEncryption()
        encryption.clear_keys()

        with self.assertRaises(EncryptionError):
            encryption.encrypt({"data": "test"})

    def test_decryption_without_key(self):
        encryption = TokenEncryption(main_password="password")
        encrypted = encryption.encrypt({"data": "test"})

        encryption.clear_keys()

        with self.assertRaises(DecryptionError):
            encryption.decrypt(encrypted)

    def test_integrity_error_on_tampered_data(self):
        encryption = TokenEncryption(main_password="password")
        encrypted = encryption.encrypt({"data": "test"})

        encrypted.hmac = b"invalid_hmac_32_bytes_signature_"

        with self.assertRaises(IntegrityError):
            encryption.decrypt(encrypted)

    def test_decryption_error_on_invalid_nonce(self):
        encryption = TokenEncryption(main_password="password")
        encrypted = encryption.encrypt({"data": "test"})

        encrypted.nonce = b"invalid_nonce"

        with self.assertRaises((DecryptionError, IntegrityError)):
            encryption.decrypt(encrypted)


class TestKeyManagement(unittest.TestCase):
    """测试密钥管理"""

    def test_clear_keys(self):
        encryption = TokenEncryption(main_password="password")

        self.assertIsNotNone(encryption._encryption_key)
        self.assertIsNotNone(encryption._hmac_key)

        encryption.clear_keys()

        self.assertIsNone(encryption._encryption_key)
        self.assertIsNone(encryption._hmac_key)
        self.assertIsNone(encryption._main_password)

    def test_rotate_keys_with_password(self):
        encryption = TokenEncryption(main_password="old_password")
        old_key = encryption._encryption_key

        encryption.rotate_keys(new_password="new_password")

        self.assertNotEqual(encryption._encryption_key, old_key)

    def test_rotate_keys_without_parameter(self):
        encryption = TokenEncryption(main_password="password")

        with self.assertRaises(ValueError):
            encryption.rotate_keys()

    def test_save_keys_to_file(self):
        encryption = TokenEncryption(main_password="password")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            temp_path = f.name

        try:
            encryption.save_keys_to_file(temp_path, protect_with_password=False)

            self.assertTrue(os.path.exists(temp_path))

            new_encryption = TokenEncryption()
            new_encryption._load_keys_from_file(temp_path)

            self.assertEqual(
                new_encryption._encryption_key,
                encryption._encryption_key
            )
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_keys_to_file_protected(self):
        encryption = TokenEncryption(main_password="password")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            temp_path = f.name

        try:
            encryption.save_keys_to_file(temp_path, protect_with_password=True)

            self.assertTrue(os.path.exists(temp_path))

            with open(temp_path) as f:
                content = f.read()

            self.assertIn("ciphertext", content)
            self.assertIn("nonce", content)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestEncryptionConstants(unittest.TestCase):
    """测试加密常量"""

    def test_key_size(self):
        self.assertEqual(TokenEncryption.KEY_SIZE, 32)

    def test_nonce_size(self):
        self.assertEqual(TokenEncryption.NONCE_SIZE, 12)

    def test_salt_size(self):
        self.assertEqual(TokenEncryption.SALT_SIZE, 16)

    def test_pbkdf2_iterations(self):
        self.assertEqual(TokenEncryption.PBKDF2_ITERATIONS, 100000)

    def test_hmac_key_size(self):
        self.assertEqual(TokenEncryption.HMAC_KEY_SIZE, 32)


class TestEdgeCases(unittest.TestCase):
    """测试边缘情况"""

    def setUp(self):
        self.encryption = TokenEncryption(main_password="test_password")

    def test_large_data_encryption(self):
        large_data = {
            "data": "x" * 1000000
        }

        encrypted = self.encryption.encrypt(large_data)
        decrypted = self.encryption.decrypt(encrypted)

        self.assertEqual(decrypted["data"], "x" * 1000000)

    def test_unicode_data(self):
        unicode_data = {
            "chinese": "你好世界",
            "emoji": "🎉🔐",
            "arabic": "مرحبا",
            "russian": "Привет"
        }

        encrypted = self.encryption.encrypt(unicode_data)
        decrypted = self.encryption.decrypt(encrypted)

        self.assertEqual(decrypted["chinese"], "你好世界")
        self.assertEqual(decrypted["emoji"], "🎉🔐")
        self.assertEqual(decrypted["arabic"], "مرحبا")
        self.assertEqual(decrypted["russian"], "Привет")

    def test_special_characters_in_password(self):
        special_password = "p@$$w0rd!#$%^&*()_+-=[]{}|;':\",./<>?"

        encryption = TokenEncryption(main_password=special_password)

        data = {"test": "data"}
        encrypted = encryption.encrypt(data)
        decrypted = encryption.decrypt(encrypted)

        self.assertEqual(decrypted["test"], "data")

    def test_minimum_password_length(self):
        encryption = TokenEncryption(main_password="a")

        data = {"test": "data"}
        encrypted = encryption.encrypt(data)
        decrypted = encryption.decrypt(encrypted)

        self.assertEqual(decrypted["test"], "data")

    def test_multiple_encrypt_decrypt_cycles(self):
        data = {"counter": 0}

        for i in range(10):
            data["counter"] = i
            encrypted = self.encryption.encrypt(data)
            decrypted = self.encryption.decrypt(encrypted)
            self.assertEqual(decrypted["counter"], i)


class TestExceptionClasses(unittest.TestCase):
    """测试异常类"""

    def test_encryption_error(self):
        with self.assertRaises(EncryptionError):
            raise EncryptionError("Test encryption error")

    def test_decryption_error(self):
        with self.assertRaises(DecryptionError):
            raise DecryptionError("Test decryption error")

    def test_integrity_error(self):
        with self.assertRaises(IntegrityError):
            raise IntegrityError("Test integrity error")

    def test_exception_inheritance(self):
        self.assertTrue(issubclass(EncryptionError, Exception))
        self.assertTrue(issubclass(DecryptionError, Exception))
        self.assertTrue(issubclass(IntegrityError, Exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
