"""
Unit tests for P2P Network Module.

Tests:
- KademliaDHT: DHT operations, k-bucket management, peer discovery
- GossipProtocol: Message propagation, deduplication, topic handling
- NATTraversal: NAT type detection, UPnP, hole punching
- P2PNode: Full node operations, message handling, peer management
"""

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from legacy.p2p_network import (
    GossipProtocol,
    KademliaDHT,
    Message,
    MessageType,
    NATTraversal,
    NATType,
    P2PNode,
    PeerInfo,
    PeerState,
)


class TestMessage(unittest.TestCase):
    """Test Message serialization and deserialization."""

    def test_message_creation(self):
        msg = Message(
            type=MessageType.PING,
            sender_id="test_node",
            payload={"key": "value"},
        )
        self.assertEqual(msg.type, MessageType.PING)
        self.assertEqual(msg.sender_id, "test_node")
        self.assertEqual(msg.payload["key"], "value")

    def test_message_serialization(self):
        msg = Message(
            type=MessageType.PING,
            sender_id="test_node",
            payload={"key": "value"},
            ttl=3600,
        )
        data = msg.to_bytes()
        self.assertIsInstance(data, bytes)

        restored = Message.from_bytes(data)
        self.assertEqual(restored.type, MessageType.PING)
        self.assertEqual(restored.sender_id, "test_node")
        self.assertEqual(restored.payload["key"], "value")
        self.assertEqual(restored.ttl, 3600)


class TestPeerInfo(unittest.TestCase):
    """Test PeerInfo dataclass."""

    def test_peer_info_creation(self):
        peer = PeerInfo(
            node_id="node123",
            ip="192.168.1.1",
            port=8765,
            capabilities={"cpu": 4, "memory": 16},
            state=PeerState.ONLINE,
        )
        self.assertEqual(peer.node_id, "node123")
        self.assertEqual(peer.ip, "192.168.1.1")
        self.assertEqual(peer.port, 8765)
        self.assertEqual(peer.capabilities["cpu"], 4)

    def test_peer_info_serialization(self):
        peer = PeerInfo(
            node_id="node123",
            ip="192.168.1.1",
            port=8765,
            capabilities={"cpu": 4},
            state=PeerState.ONLINE,
            last_seen=12345.0,
        )

        data = peer.to_dict()
        restored = PeerInfo.from_dict(data)

        self.assertEqual(restored.node_id, peer.node_id)
        self.assertEqual(restored.ip, peer.ip)
        self.assertEqual(restored.port, peer.port)
        self.assertEqual(restored.state, PeerState.ONLINE)


class TestKademliaDHT(unittest.TestCase):
    """Test Kademlia DHT implementation."""

    def setUp(self):
        self.dht = KademliaDHT("test_node_1")

    def test_dht_initialization(self):
        self.assertEqual(self.dht.node_id, "test_node_1")
        self.assertEqual(len(self.dht.k_buckets), KademliaDHT.ID_BITS)
        self.assertEqual(len(self.dht.storage), 0)

    def test_xor_distance(self):
        id1 = 0b1010
        id2 = 0b1100
        distance = self.dht._xor_distance(id1, id2)
        self.assertEqual(distance, 0b0110)

    def test_add_peer(self):
        peer = PeerInfo(
            node_id="peer1",
            ip="192.168.1.2",
            port=8765,
            state=PeerState.ONLINE,
        )
        result = self.dht.add_peer(peer)
        self.assertTrue(result)

        retrieved = self.dht.get_peer("peer1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.node_id, "peer1")

    def test_remove_peer(self):
        peer = PeerInfo(
            node_id="peer1",
            ip="192.168.1.2",
            port=8765,
        )
        self.dht.add_peer(peer)
        result = self.dht.remove_peer("peer1")
        self.assertTrue(result)

        retrieved = self.dht.get_peer("peer1")
        self.assertIsNone(retrieved)

    def test_find_closest_peers(self):
        peers = [
            PeerInfo(node_id=f"peer{i}", ip=f"192.168.1.{i}", port=8765)
            for i in range(5)
        ]

        for peer in peers:
            self.dht.add_peer(peer)

        closest = self.dht.find_closest_peers("target", count=3)
        self.assertEqual(len(closest), 3)

    def test_store_and_get(self):
        self.dht.store("key1", "value1", ttl=3600)
        value = self.dht.get("key1")
        self.assertEqual(value, "value1")

    def test_store_with_expiry(self):
        self.dht.store("key1", "value1", ttl=0.1)
        time.sleep(0.2)
        value = self.dht.get("key1")
        self.assertIsNone(value)

    def test_get_all_peers(self):
        peers = [
            PeerInfo(node_id=f"peer{i}", ip=f"192.168.1.{i}", port=8765)
            for i in range(3)
        ]

        for peer in peers:
            self.dht.add_peer(peer)

        all_peers = self.dht.get_all_peers()
        self.assertEqual(len(all_peers), 3)

    def test_get_stats(self):
        stats = self.dht.get_stats()
        self.assertIn("node_id", stats)
        self.assertIn("total_peers", stats)
        self.assertIn("stored_items", stats)


class TestGossipProtocol(unittest.TestCase):
    """Test Gossip Protocol implementation."""

    def setUp(self):
        self.dht = KademliaDHT("test_node")
        self.gossip = GossipProtocol("test_node", self.dht)

    def test_gossip_initialization(self):
        self.assertEqual(self.gossip.node_id, "test_node")
        self.assertEqual(self.gossip.fanout, GossipProtocol.DEFAULT_FANOUT)
        self.assertEqual(len(self.gossip.message_cache), 0)

    def test_register_handler(self):
        handler = MagicMock()
        self.gossip.register_handler("test_topic", handler)
        self.assertIn("test_topic", self.gossip.topic_handlers)

    def test_unregister_handler(self):
        handler = MagicMock()
        self.gossip.register_handler("test_topic", handler)
        self.gossip.unregister_handler("test_topic")
        self.assertNotIn("test_topic", self.gossip.topic_handlers)

    def test_message_deduplication(self):
        msg_id = "test_message_123"

        is_seen_first = self.gossip._is_message_seen(msg_id)
        self.assertFalse(is_seen_first)

        is_seen_second = self.gossip._is_message_seen(msg_id)
        self.assertTrue(is_seen_second)

    def test_select_gossip_peers(self):
        peers = [
            PeerInfo(
                node_id=f"peer{i}",
                ip=f"192.168.1.{i}",
                port=8765,
                state=PeerState.ONLINE,
            )
            for i in range(10)
        ]

        for peer in peers:
            self.dht.add_peer(peer)

        selected = self.gossip.select_gossip_peers()
        self.assertLessEqual(len(selected), self.gossip.fanout)

    def test_cleanup_cache(self):
        for i in range(5):
            self.gossip.message_cache[f"msg_{i}"] = time.time() - 7200

        self.gossip._cleanup_cache()

        for i in range(5):
            self.assertNotIn(f"msg_{i}", self.gossip.message_cache)

    def test_get_stats(self):
        stats = self.gossip.get_stats()
        self.assertIn("cached_messages", stats)
        self.assertIn("registered_topics", stats)
        self.assertIn("fanout", stats)


class TestNATTraversal(unittest.TestCase):
    """Test NAT Traversal implementation."""

    def setUp(self):
        self.nat = NATTraversal(local_port=8765)

    def test_nat_initialization(self):
        self.assertEqual(self.nat.local_port, 8765)
        self.assertEqual(self.nat.nat_type, NATType.UNKNOWN)
        self.assertIsNone(self.nat.external_ip)

    def test_get_local_ip(self):
        local_ip = self.nat.get_local_ip()
        self.assertIsNotNone(local_ip)

    @patch("socket.socket")
    def test_check_public_ip(self, mock_socket):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"192.168.1.1"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            with patch.object(self.nat, "get_local_ip", return_value="192.168.1.1"):
                result = self.nat._check_public_ip()
                self.assertTrue(result)

    def test_get_stats(self):
        stats = self.nat.get_stats()
        self.assertIn("nat_type", stats)
        self.assertIn("external_ip", stats)
        self.assertIn("upnp_available", stats)


class TestP2PNode(unittest.TestCase):
    """Test P2P Node implementation."""

    def setUp(self):
        self.node = P2PNode(
            node_id="test_node",
            port=18765,
            capabilities={"cpu": 4, "memory": 16},
        )

    def test_node_initialization(self):
        self.assertEqual(self.node.node_id, "test_node")
        self.assertEqual(self.node.port, 18765)
        self.assertEqual(self.node.capabilities["cpu"], 4)
        self.assertIsNotNone(self.node.dht)
        self.assertIsNotNone(self.node.gossip)
        self.assertIsNotNone(self.node.nat)

    def test_generate_node_id(self):
        node_id = self.node._generate_node_id()
        self.assertEqual(len(node_id), 32)
        self.assertIsInstance(node_id, str)

    def test_register_handler(self):
        handler = MagicMock()
        self.node.register_handler(MessageType.TASK_REQUEST, handler)
        self.assertIn(MessageType.TASK_REQUEST, self.node._message_handlers)

    def test_get_stats(self):
        stats = self.node.get_stats()
        self.assertIn("node_id", stats)
        self.assertIn("port", stats)
        self.assertIn("running", stats)
        self.assertIn("peers", stats)
        self.assertIn("dht", stats)
        self.assertIn("gossip", stats)
        self.assertIn("nat", stats)


class TestP2PNodeAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for P2P Node."""

    async def asyncSetUp(self):
        self.node = P2PNode(
            node_id="async_test_node",
            port=18766,
        )

    async def asyncTearDown(self):
        if self.node._running:
            await self.node.stop()

    async def test_start_and_stop(self):
        result = await self.node.start()
        self.assertTrue(result)
        self.assertTrue(self.node._running)

        await self.node.stop()
        self.assertFalse(self.node._running)

    async def test_handle_ping(self):
        message = Message(
            type=MessageType.PING,
            sender_id="remote_node",
            message_id="ping_123",
        )

        peer = PeerInfo(
            node_id="remote_node",
            ip="192.168.1.100",
            port=8765,
        )
        self.node._peers["remote_node"] = peer

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        await self.node._handle_ping(message, mock_writer)

        mock_writer.write.assert_called()

    async def test_handle_find_node(self):
        peer = PeerInfo(
            node_id="peer1",
            ip="192.168.1.2",
            port=8765,
        )
        self.node.dht.add_peer(peer)

        message = Message(
            type=MessageType.FIND_NODE,
            sender_id="remote_node",
            payload={"target_id": "some_target"},
        )

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        await self.node._handle_find_node(message, mock_writer)

        mock_writer.write.assert_called()

    async def test_handle_store(self):
        message = Message(
            type=MessageType.STORE,
            sender_id="remote_node",
            payload={"key": "test_key", "value": "test_value", "ttl": 3600},
        )

        await self.node._handle_store(message)

        value = self.node.dht.get("test_key")
        self.assertEqual(value, "test_value")

    async def test_handle_find_value(self):
        self.node.dht.store("test_key", "test_value")

        message = Message(
            type=MessageType.FIND_VALUE,
            sender_id="remote_node",
            payload={"key": "test_key"},
        )

        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()

        await self.node._handle_find_value(message, mock_writer)

        mock_writer.write.assert_called()

    async def test_handle_peer_disconnect(self):
        peer = PeerInfo(
            node_id="disconnecting_peer",
            ip="192.168.1.3",
            port=8765,
        )
        self.node._peers["disconnecting_peer"] = peer
        self.node.dht.add_peer(peer)

        message = Message(
            type=MessageType.PEER_DISCONNECT,
            sender_id="disconnecting_peer",
        )

        await self.node._handle_peer_disconnect(message)

        self.assertNotIn("disconnecting_peer", self.node._peers)

    async def test_store_value(self):
        peer = PeerInfo(
            node_id="peer1",
            ip="192.168.1.2",
            port=8765,
            state=PeerState.ONLINE,
        )
        self.node.dht.add_peer(peer)

        with patch.object(self.node, "_send_to_peer", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await self.node.store_value("key1", "value1")
            self.assertTrue(result)

            value = self.node.dht.get("key1")
            self.assertEqual(value, "value1")


class TestIntegration(unittest.TestCase):
    """Integration tests for P2P Network."""

    def test_message_flow(self):
        dht1 = KademliaDHT("node1")
        dht2 = KademliaDHT("node2")

        peer1 = PeerInfo(node_id="node1", ip="192.168.1.1", port=8765)
        peer2 = PeerInfo(node_id="node2", ip="192.168.1.2", port=8765)

        dht1.add_peer(peer2)
        dht2.add_peer(peer1)

        self.assertEqual(len(dht1.get_all_peers()), 1)
        self.assertEqual(len(dht2.get_all_peers()), 1)

    def test_dht_replication(self):
        nodes = [KademliaDHT(f"node{i}") for i in range(5)]

        for i, node in enumerate(nodes):
            for j, other in enumerate(nodes):
                if i != j:
                    peer = PeerInfo(
                        node_id=other.node_id,
                        ip=f"192.168.1.{j}",
                        port=8765,
                    )
                    node.add_peer(peer)

        nodes[0].store("shared_key", "shared_value")

        value = nodes[0].get("shared_key")
        self.assertEqual(value, "shared_value")

    def test_gossip_propagation(self):
        dht = KademliaDHT("gossip_node")
        gossip = GossipProtocol("gossip_node", dht)

        received_messages = []

        def handler(data):
            received_messages.append(data)

        gossip.register_handler("test_topic", handler)

        message = Message(
            type=MessageType.GOSSIP,
            sender_id="remote_node",
            payload={"topic": "test_topic", "data": {"message": "hello"}},
        )

        asyncio.run(gossip.handle_message(message))

        self.assertEqual(len(received_messages), 1)
        self.assertEqual(received_messages[0]["message"], "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
