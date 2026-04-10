"""
Tests for P2P Network Security Module.
"""

import pytest

from legacy.p2p_network.security import (
    CRYPTO_AVAILABLE,
    EncryptedMessage,
    MessageCipher,
    NodeIdentity,
    SecureSession,
)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestNodeIdentity:
    """Test NodeIdentity class."""

    def test_generate_identity(self):
        """Test generating a new node identity."""
        identity = NodeIdentity.generate()

        assert identity.node_id is not None
        assert len(identity.node_id) == 32
        assert identity.public_key is not None
        assert identity.private_key is not None
        assert len(identity.public_key) == 32
        assert len(identity.private_key) == 32

    def test_generate_identity_with_id(self):
        """Test generating identity with specific ID."""
        identity = NodeIdentity.generate(node_id="test-node-123")

        assert identity.node_id == "test-node-123"

    def test_sign_and_verify(self):
        """Test signing and verifying data."""
        identity = NodeIdentity.generate()
        data = b"test message to sign"

        signature = identity.sign(data)
        assert signature is not None
        assert len(signature) == 64

        assert identity.verify(data, signature) is True

        assert identity.verify(b"different data", signature) is False

    def test_cross_verify(self):
        """Test verification with different keys."""
        identity1 = NodeIdentity.generate()
        identity2 = NodeIdentity.generate()

        data = b"test message"
        signature = identity1.sign(data)

        assert identity2.verify(data, signature, identity1.public_key) is True
        assert identity2.verify(data, signature, identity2.public_key) is False

    def test_trust_node(self):
        """Test trusting nodes."""
        identity = NodeIdentity.generate()
        other_identity = NodeIdentity.generate()

        assert identity.is_trusted(other_identity.node_id) is False

        identity.trust_node(other_identity.node_id, other_identity.public_key)

        assert identity.is_trusted(other_identity.node_id) is True
        assert identity.get_trusted_public_key(other_identity.node_id) == other_identity.public_key

    def test_to_dict(self):
        """Test serialization."""
        identity = NodeIdentity.generate(node_id="test-node")
        identity.trust_node("other-node", b"fake-public-key")

        data = identity.to_dict()

        assert data["node_id"] == "test-node"
        assert "public_key" in data
        assert "private_key" not in data
        assert "trusted_nodes" in data


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestMessageCipher:
    """Test MessageCipher class."""

    def test_generate_key(self):
        """Test key generation."""
        key = MessageCipher.generate_key()

        assert len(key) == 32

    def test_derive_key(self):
        """Test key derivation."""
        shared_secret = b"shared-secret-123"
        salt = b"test-salt"

        key1 = MessageCipher.derive_key(shared_secret, salt)
        key2 = MessageCipher.derive_key(shared_secret, salt)

        assert key1 == key2
        assert len(key1) == 32

    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        cipher = MessageCipher()
        plaintext = b"secret message"

        nonce, ciphertext = cipher.encrypt(plaintext)

        assert nonce is not None
        assert ciphertext is not None
        assert len(nonce) == 12
        assert ciphertext != plaintext

        decrypted = cipher.decrypt(nonce, ciphertext)

        assert decrypted == plaintext

    def test_encrypt_decrypt_with_associated_data(self):
        """Test encryption with associated data."""
        cipher = MessageCipher()
        plaintext = b"secret message"
        aad = b"additional authenticated data"

        nonce, ciphertext = cipher.encrypt(plaintext, aad)

        decrypted = cipher.decrypt(nonce, ciphertext, aad)
        assert decrypted == plaintext

        decrypted_wrong = cipher.decrypt(nonce, ciphertext, b"wrong aad")
        assert decrypted_wrong is None

    def test_decrypt_fails_with_wrong_key(self):
        """Test decryption fails with wrong key."""
        cipher1 = MessageCipher()
        cipher2 = MessageCipher()

        plaintext = b"secret message"
        nonce, ciphertext = cipher1.encrypt(plaintext)

        decrypted = cipher2.decrypt(nonce, ciphertext)
        assert decrypted is None

    def test_encrypt_message(self):
        """Test message encryption."""
        cipher = MessageCipher()
        identity = NodeIdentity.generate()
        message = b"test message"

        encrypted = cipher.encrypt_message(message, identity.node_id, identity)

        assert encrypted.sender_id == identity.node_id
        assert encrypted.nonce is not None
        assert encrypted.ciphertext is not None
        assert encrypted.signature is not None

    def test_decrypt_message(self):
        """Test message decryption."""
        cipher = MessageCipher()
        identity = NodeIdentity.generate()
        message = b"test message"

        encrypted = cipher.encrypt_message(message, identity.node_id, identity)

        decrypted = cipher.decrypt_message(encrypted, identity)

        assert decrypted == message


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography library not installed")
class TestSecureSession:
    """Test SecureSession class."""

    def test_initiate_handshake(self):
        """Test handshake initiation."""
        identity = NodeIdentity.generate()
        session = SecureSession(identity)

        handshake = session.initiate_handshake("peer-123")

        assert handshake["type"] == "handshake_init"
        assert handshake["sender_id"] == identity.node_id
        assert "public_key" in handshake
        assert "nonce" in handshake
        assert "signature" in handshake

    def test_complete_handshake(self):
        """Test complete handshake flow."""
        identity1 = NodeIdentity.generate()
        identity2 = NodeIdentity.generate()

        session1 = SecureSession(identity1)
        session2 = SecureSession(identity2)

        handshake_init = session1.initiate_handshake(identity2.node_id)

        handshake_response = session2.process_handshake_init(handshake_init)

        assert handshake_response is not None
        assert handshake_response["type"] == "handshake_response"

        success = session1.complete_handshake(identity2.node_id, handshake_response)
        assert success is True

        assert session1.has_session(identity2.node_id) is True
        assert session2.has_session(identity1.node_id) is True

    def test_encrypt_for_peer(self):
        """Test encrypting message for peer."""
        identity1 = NodeIdentity.generate()
        identity2 = NodeIdentity.generate()

        session1 = SecureSession(identity1)
        session2 = SecureSession(identity2)

        handshake_init = session1.initiate_handshake(identity2.node_id)
        handshake_response = session2.process_handshake_init(handshake_init)
        session1.complete_handshake(identity2.node_id, handshake_response)

        message = b"secret message for peer"
        encrypted = session1.encrypt_for_peer(identity2.node_id, message)

        assert encrypted is not None
        assert encrypted.sender_id == identity1.node_id

    def test_decrypt_from_peer(self):
        """Test decrypting message from peer."""
        identity1 = NodeIdentity.generate()
        identity2 = NodeIdentity.generate()

        session1 = SecureSession(identity1)
        session2 = SecureSession(identity2)

        handshake_init = session1.initiate_handshake(identity2.node_id)
        handshake_response = session2.process_handshake_init(handshake_init)
        session1.complete_handshake(identity2.node_id, handshake_response)

        message = b"secret message for peer"
        encrypted = session1.encrypt_for_peer(identity2.node_id, message)

        assert encrypted is not None, "Encryption should succeed"

        decrypted = session2.decrypt_from_peer(encrypted)

        assert decrypted == message

    def test_end_session(self):
        """Test ending a session."""
        identity1 = NodeIdentity.generate()
        identity2 = NodeIdentity.generate()

        session1 = SecureSession(identity1)
        session2 = SecureSession(identity2)

        handshake_init = session1.initiate_handshake(identity2.node_id)
        handshake_response = session2.process_handshake_init(handshake_init)
        session1.complete_handshake(identity2.node_id, handshake_response)

        assert session1.has_session(identity2.node_id) is True

        session1.end_session(identity2.node_id)

        assert session1.has_session(identity2.node_id) is False


class TestEncryptedMessage:
    """Test EncryptedMessage class."""

    def test_to_bytes_and_from_bytes(self):
        """Test serialization and deserialization."""
        msg = EncryptedMessage(
            sender_id="test-node",
            nonce=b"123456789012",
            ciphertext=b"encrypted-data-here",
            signature=b"signature-bytes",
        )

        data = msg.to_bytes()

        assert isinstance(data, bytes)

        restored = EncryptedMessage.from_bytes(data)

        assert restored.sender_id == msg.sender_id
        assert restored.nonce == msg.nonce
        assert restored.ciphertext == msg.ciphertext
        assert restored.signature == msg.signature
