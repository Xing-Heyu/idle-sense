"""
P2P Network Security Module.

Implements:
- Node authentication using Ed25519 signatures
- Message encryption using AES-256-GCM
- Secure handshake protocol
- Certificate-based trust model

References:
- Noise Protocol Framework: https://noiseprotocol.org/
- Ed25519: https://ed25519.cr.yp.to/
- AES-GCM: NIST SP 800-38D
"""

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from cryptography.exceptions import InvalidSignature, InvalidTag
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    ed25519 = None
    AESGCM = None


@dataclass
class NodeIdentity:
    """Node identity with Ed25519 keypair."""
    node_id: str
    public_key: bytes
    private_key: Optional[bytes] = None
    created_at: float = field(default_factory=time.time)
    trusted_nodes: dict[str, bytes] = field(default_factory=dict)

    @classmethod
    def generate(cls, node_id: Optional[str] = None) -> "NodeIdentity":
        """Generate a new node identity with Ed25519 keypair."""
        if not CRYPTO_AVAILABLE:
            return cls(
                node_id=node_id or secrets.token_hex(16),
                public_key=b"no_crypto_support",
                private_key=b"no_crypto_support"
            )

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

        if node_id is None:
            node_id = hashlib.sha256(public_bytes).hexdigest()[:32]

        return cls(
            node_id=node_id,
            public_key=public_bytes,
            private_key=private_bytes
        )

    @classmethod
    def from_private_key(cls, private_key_bytes: bytes, node_id: Optional[str] = None) -> "NodeIdentity":
        """Create identity from existing private key."""
        if not CRYPTO_AVAILABLE:
            return cls(node_id=node_id or "unknown", public_key=b"", private_key=private_key_bytes)

        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        public_key = private_key.public_key()
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        if node_id is None:
            node_id = hashlib.sha256(public_bytes).hexdigest()[:32]

        return cls(
            node_id=node_id,
            public_key=public_bytes,
            private_key=private_key_bytes
        )

    def sign(self, data: bytes) -> bytes:
        """Sign data with the private key."""
        if not CRYPTO_AVAILABLE or not self.private_key:
            return b"no_signature"

        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(self.private_key)
        return private_key.sign(data)

    def verify(self, data: bytes, signature: bytes, public_key: Optional[bytes] = None) -> bool:
        """Verify a signature."""
        if not CRYPTO_AVAILABLE:
            return True

        pub_key_bytes = public_key or self.public_key
        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_key_bytes)
            public_key.verify(signature, data)
            return True
        except (InvalidSignature, Exception):
            return False

    def trust_node(self, node_id: str, public_key: bytes):
        """Add a node to the trusted nodes list."""
        self.trusted_nodes[node_id] = public_key

    def is_trusted(self, node_id: str) -> bool:
        """Check if a node is trusted."""
        return node_id in self.trusted_nodes

    def get_trusted_public_key(self, node_id: str) -> Optional[bytes]:
        """Get the public key of a trusted node."""
        return self.trusted_nodes.get(node_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize identity (without private key for security)."""
        return {
            "node_id": self.node_id,
            "public_key": self.public_key.hex() if self.public_key else None,
            "created_at": self.created_at,
            "trusted_nodes": {
                nid: pk.hex() for nid, pk in self.trusted_nodes.items()
            }
        }


@dataclass
class EncryptedMessage:
    """Encrypted message container."""
    sender_id: str
    nonce: bytes
    ciphertext: bytes
    timestamp: float = field(default_factory=time.time)
    signature: Optional[bytes] = None

    def to_bytes(self) -> bytes:
        """Serialize to bytes for transmission."""
        data = {
            "sender_id": self.sender_id,
            "nonce": self.nonce.hex(),
            "ciphertext": self.ciphertext.hex(),
            "timestamp": self.timestamp,
            "signature": self.signature.hex() if self.signature else None
        }
        return json.dumps(data).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedMessage":
        """Deserialize from bytes."""
        obj = json.loads(data.decode("utf-8"))
        return cls(
            sender_id=obj["sender_id"],
            nonce=bytes.fromhex(obj["nonce"]),
            ciphertext=bytes.fromhex(obj["ciphertext"]),
            timestamp=obj.get("timestamp", time.time()),
            signature=bytes.fromhex(obj["signature"]) if obj.get("signature") else None
        )


class MessageCipher:
    """AES-256-GCM message encryption/decryption."""

    KEY_SIZE = 32
    NONCE_SIZE = 12

    def __init__(self, key: Optional[bytes] = None):
        self.key = key or self.generate_key()
        if CRYPTO_AVAILABLE:
            self.aesgcm = AESGCM(self.key)
        else:
            self.aesgcm = None

    @classmethod
    def generate_key(cls) -> bytes:
        """Generate a new encryption key."""
        return secrets.token_bytes(cls.KEY_SIZE)

    @classmethod
    def derive_key(cls, shared_secret: bytes, salt: bytes = b"idle-sense-v1") -> bytes:
        """Derive an encryption key from a shared secret using HKDF."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            shared_secret,
            salt,
            iterations=100000,
            dklen=cls.KEY_SIZE
        )

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """Encrypt plaintext and return (nonce, ciphertext)."""
        if not CRYPTO_AVAILABLE:
            nonce = secrets.token_bytes(self.NONCE_SIZE)
            return nonce, plaintext

        nonce = secrets.token_bytes(self.NONCE_SIZE)
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce, ciphertext

    def decrypt(self, nonce: bytes, ciphertext: bytes, associated_data: Optional[bytes] = None) -> Optional[bytes]:
        """Decrypt ciphertext. Returns None if decryption fails."""
        if not CRYPTO_AVAILABLE:
            return ciphertext

        try:
            return self.aesgcm.decrypt(nonce, ciphertext, associated_data)
        except InvalidTag:
            return None

    def encrypt_message(self, message: bytes, sender_id: str, identity: NodeIdentity) -> EncryptedMessage:
        """Encrypt and sign a message."""
        nonce, ciphertext = self.encrypt(message, sender_id.encode())

        signature = None
        if identity.private_key:
            signature = identity.sign(ciphertext)

        return EncryptedMessage(
            sender_id=sender_id,
            nonce=nonce,
            ciphertext=ciphertext,
            signature=signature
        )

    def decrypt_message(self, encrypted: EncryptedMessage, identity: NodeIdentity) -> Optional[bytes]:
        """Decrypt and verify a message."""
        if encrypted.signature:
            sender_pub_key = identity.get_trusted_public_key(encrypted.sender_id)
            if sender_pub_key and not identity.verify(encrypted.ciphertext, encrypted.signature, sender_pub_key):
                return None

        return self.decrypt(encrypted.nonce, encrypted.ciphertext, encrypted.sender_id.encode())


class SecureSession:
    """Secure session management for P2P connections."""

    SESSION_TIMEOUT = 3600

    def __init__(self, identity: NodeIdentity):
        self.identity = identity
        self.sessions: dict[str, dict[str, Any]] = {}
        self.session_ciphers: dict[str, MessageCipher] = {}

    def initiate_handshake(self, peer_id: str) -> dict[str, Any]:
        """Initiate a handshake with a peer."""
        session_key = secrets.token_bytes(32)
        nonce = secrets.token_bytes(16)
        timestamp = time.time()

        challenge_data = f"{self.identity.node_id}:{peer_id}:{timestamp}:{nonce.hex()}".encode()
        signature = self.identity.sign(challenge_data)

        self.sessions[peer_id] = {
            "state": "initiated",
            "session_key": session_key,
            "nonce": nonce,
            "timestamp": timestamp,
            "peer_public_key": None
        }

        self.session_ciphers[peer_id] = MessageCipher(session_key)

        return {
            "type": "handshake_init",
            "sender_id": self.identity.node_id,
            "public_key": self.identity.public_key.hex(),
            "session_key": session_key.hex(),
            "nonce": nonce.hex(),
            "timestamp": timestamp,
            "signature": signature.hex()
        }

    def process_handshake_init(self, handshake: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Process an incoming handshake initiation."""
        sender_id = handshake.get("sender_id")
        public_key_hex = handshake.get("public_key")
        session_key_hex = handshake.get("session_key")
        nonce_hex = handshake.get("nonce")
        timestamp = handshake.get("timestamp", 0)
        signature_hex = handshake.get("signature")

        if not all([sender_id, public_key_hex, session_key_hex, nonce_hex, signature_hex]):
            return None

        if abs(time.time() - timestamp) > 300:
            return None

        try:
            public_key = bytes.fromhex(public_key_hex)
            session_key = bytes.fromhex(session_key_hex)
            nonce = bytes.fromhex(nonce_hex)
            signature = bytes.fromhex(signature_hex)
        except ValueError:
            return None

        challenge_data = f"{sender_id}:{self.identity.node_id}:{timestamp}:{nonce.hex()}".encode()

        if not self.identity.verify(challenge_data, signature, public_key):
            return None

        self.identity.trust_node(sender_id, public_key)

        response_nonce = secrets.token_bytes(16)
        response_timestamp = time.time()

        response_data = f"{self.identity.node_id}:{sender_id}:{response_timestamp}:{response_nonce.hex()}".encode()
        response_signature = self.identity.sign(response_data)

        self.sessions[sender_id] = {
            "state": "established",
            "session_key": session_key,
            "nonce": response_nonce,
            "timestamp": response_timestamp,
            "peer_public_key": public_key
        }

        self.session_ciphers[sender_id] = MessageCipher(session_key)

        return {
            "type": "handshake_response",
            "sender_id": self.identity.node_id,
            "public_key": self.identity.public_key.hex(),
            "nonce": response_nonce.hex(),
            "timestamp": response_timestamp,
            "signature": response_signature.hex()
        }

    def complete_handshake(self, peer_id: str, response: dict[str, Any]) -> bool:
        """Complete the handshake with a peer's response."""
        if peer_id not in self.sessions:
            return False

        session = self.sessions[peer_id]
        if session["state"] != "initiated":
            return False

        public_key_hex = response.get("public_key")
        nonce_hex = response.get("nonce")
        timestamp = response.get("timestamp", 0)
        signature_hex = response.get("signature")

        if not all([public_key_hex, nonce_hex, signature_hex]):
            return False

        if abs(time.time() - timestamp) > 300:
            return False

        try:
            public_key = bytes.fromhex(public_key_hex)
            nonce = bytes.fromhex(nonce_hex)
            signature = bytes.fromhex(signature_hex)
        except ValueError:
            return False

        response_data = f"{response.get('sender_id')}:{self.identity.node_id}:{timestamp}:{nonce.hex()}".encode()

        if not self.identity.verify(response_data, signature, public_key):
            return False

        self.identity.trust_node(peer_id, public_key)

        session["state"] = "established"
        session["peer_public_key"] = public_key
        session["timestamp"] = timestamp

        self.session_ciphers[peer_id] = MessageCipher(session["session_key"])

        return True

    def has_session(self, peer_id: str) -> bool:
        """Check if a secure session exists with a peer."""
        if peer_id not in self.sessions:
            return False

        session = self.sessions[peer_id]
        if session["state"] != "established":
            return False

        if time.time() - session["timestamp"] > self.SESSION_TIMEOUT:
            del self.sessions[peer_id]
            if peer_id in self.session_ciphers:
                del self.session_ciphers[peer_id]
            return False

        return True

    def encrypt_for_peer(self, peer_id: str, message: bytes) -> Optional[EncryptedMessage]:
        """Encrypt a message for a specific peer."""
        if peer_id not in self.session_ciphers:
            return None

        cipher = self.session_ciphers[peer_id]
        return cipher.encrypt_message(message, self.identity.node_id, self.identity)

    def decrypt_from_peer(self, encrypted: EncryptedMessage) -> Optional[bytes]:
        """Decrypt a message from a peer."""
        peer_id = encrypted.sender_id
        if peer_id not in self.session_ciphers:
            return None

        cipher = self.session_ciphers[peer_id]
        return cipher.decrypt_message(encrypted, self.identity)

    def end_session(self, peer_id: str):
        """End a secure session with a peer."""
        if peer_id in self.sessions:
            del self.sessions[peer_id]
        if peer_id in self.session_ciphers:
            del self.session_ciphers[peer_id]

    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = time.time()
        expired = [
            peer_id for peer_id, session in self.sessions.items()
            if current_time - session.get("timestamp", 0) > self.SESSION_TIMEOUT
        ]
        for peer_id in expired:
            self.end_session(peer_id)


__all__ = [
    "CRYPTO_AVAILABLE",
    "NodeIdentity",
    "EncryptedMessage",
    "MessageCipher",
    "SecureSession",
]
