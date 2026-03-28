"""
Unit tests for Distributed Storage Module.

Tests:
- CacheLayer: LRU cache, TTL, statistics
- DistributedLock: Acquisition, release, timeout
- MemoryDistributedStorage: Basic operations
- ShardedStorage: Consistent hashing, replication
"""

import asyncio
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from legacy.storage.distributed import (
    CacheLayer,
    ConsistencyLevel,
    MemoryDistributedStorage,
    ShardedStorage,
    StorageConfig,
    create_distributed_storage,
)


class TestStorageConfig(unittest.TestCase):
    """Test StorageConfig dataclass."""

    def test_config_defaults(self):
        config = StorageConfig()

        self.assertEqual(config.backend, "memory")
        self.assertEqual(config.ttl, 86400)
        self.assertEqual(config.replication_factor, 1)
        self.assertEqual(config.consistency_level, ConsistencyLevel.QUORUM)
        self.assertTrue(config.cache_enabled)

    def test_config_custom(self):
        config = StorageConfig(
            backend="redis",
            ttl=3600,
            replication_factor=3,
            consistency_level=ConsistencyLevel.ALL,
        )

        self.assertEqual(config.backend, "redis")
        self.assertEqual(config.ttl, 3600)
        self.assertEqual(config.replication_factor, 3)
        self.assertEqual(config.consistency_level, ConsistencyLevel.ALL)

    def test_config_serialization(self):
        config = StorageConfig(backend="etcd", ttl=7200)
        data = config.to_dict()

        self.assertEqual(data["backend"], "etcd")
        self.assertEqual(data["ttl"], 7200)


class TestCacheLayer(unittest.TestCase):
    """Test CacheLayer implementation."""

    def setUp(self):
        self.cache = CacheLayer(max_size=5, default_ttl=60)

    def test_cache_set_get(self):
        self.cache.set("key1", "value1")

        result = self.cache.get("key1")

        self.assertEqual(result, "value1")

    def test_cache_miss(self):
        result = self.cache.get("nonexistent")

        self.assertIsNone(result)
        self.assertEqual(self.cache._misses, 1)

    def test_cache_ttl_expiry(self):
        cache = CacheLayer(max_size=5, default_ttl=0.1)

        cache.set("key1", "value1")

        time.sleep(0.2)

        result = cache.get("key1")

        self.assertIsNone(result)

    def test_cache_lru_eviction(self):
        cache = CacheLayer(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")

        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key2"), "value2")
        self.assertEqual(cache.get("key3"), "value3")
        self.assertEqual(cache.get("key4"), "value4")

    def test_cache_delete(self):
        self.cache.set("key1", "value1")

        result = self.cache.delete("key1")

        self.assertTrue(result)
        self.assertIsNone(self.cache.get("key1"))

    def test_cache_clear(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        self.cache.clear()

        self.assertEqual(len(self.cache._cache), 0)

    def test_cache_stats(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("nonexistent")

        stats = self.cache.get_stats()

        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["size"], 1)


class TestMemoryDistributedStorage(unittest.TestCase):
    """Test MemoryDistributedStorage implementation."""

    def setUp(self):
        self.config = StorageConfig(backend="memory", cache_enabled=False)
        self.storage = MemoryDistributedStorage(self.config)

    def test_storage_initialization(self):
        self.assertEqual(len(self.storage._data), 0)

    def test_put_get(self):
        async def test():
            await self.storage.put("key1", {"data": "value1"})
            result = await self.storage.get("key1")

            self.assertEqual(result["data"], "value1")

        asyncio.run(test())

    def test_get_nonexistent(self):
        async def test():
            result = await self.storage.get("nonexistent")

            self.assertIsNone(result)

        asyncio.run(test())

    def test_delete(self):
        async def test():
            await self.storage.put("key1", "value1")
            result = await self.storage.delete("key1")

            self.assertTrue(result)

            result = await self.storage.get("key1")
            self.assertIsNone(result)

        asyncio.run(test())

    def test_exists(self):
        async def test():
            await self.storage.put("key1", "value1")

            self.assertTrue(await self.storage.exists("key1"))
            self.assertFalse(await self.storage.exists("nonexistent"))

        asyncio.run(test())

    def test_keys(self):
        async def test():
            await self.storage.put("key1", "value1")
            await self.storage.put("key2", "value2")
            await self.storage.put("other", "value3")

            keys = await self.storage.keys("key*")

            self.assertEqual(len(keys), 2)
            self.assertIn("key1", keys)
            self.assertIn("key2", keys)

        asyncio.run(test())

    def test_ttl_expiry(self):
        async def test():
            config = StorageConfig(backend="memory", ttl=0.1, cache_enabled=False)
            storage = MemoryDistributedStorage(config)

            await storage.put("key1", "value1")

            await asyncio.sleep(0.2)

            result = await storage.get("key1")

            self.assertIsNone(result)

        asyncio.run(test())

    def test_nx_flag(self):
        async def test():
            result1 = await self.storage.put("key1", "value1", nx=True)
            result2 = await self.storage.put("key1", "value2", nx=True)

            self.assertTrue(result1)
            self.assertFalse(result2)

            result = await self.storage.get("key1")
            self.assertEqual(result, "value1")

        asyncio.run(test())

    def test_get_stats(self):
        async def test():
            await self.storage.put("key1", "value1")
            await self.storage.put("key2", "value2")

            stats = await self.storage.get_stats()

            self.assertEqual(stats["backend"], "memory")
            self.assertEqual(stats["total_keys"], 2)

        asyncio.run(test())


class TestDistributedLock(unittest.TestCase):
    """Test DistributedLock implementation."""

    def setUp(self):
        self.config = StorageConfig(backend="memory", cache_enabled=False)
        self.storage = MemoryDistributedStorage(self.config)

    def test_lock_acquire_release(self):
        async def test():
            lock = self.storage.create_lock("test_lock")

            acquired = await lock.acquire(timeout=1.0)

            self.assertTrue(acquired)
            self.assertTrue(lock._acquired)

            released = await lock.release()

            self.assertTrue(released)
            self.assertFalse(lock._acquired)

        asyncio.run(test())

    def test_lock_contention(self):
        async def test():
            lock1 = self.storage.create_lock("shared_lock")
            lock2 = self.storage.create_lock("shared_lock")

            acquired1 = await lock1.acquire(timeout=1.0)
            self.assertTrue(acquired1)

            acquired2 = await lock2.acquire(timeout=0.5)
            self.assertFalse(acquired2)

            await lock1.release()

            acquired2 = await lock2.acquire(timeout=1.0)
            self.assertTrue(acquired2)

            await lock2.release()

        asyncio.run(test())

    def test_lock_context_manager(self):
        async def test():
            async with self.storage.create_lock("ctx_lock") as lock:
                self.assertTrue(lock._acquired)

            self.assertFalse(lock._acquired)

        asyncio.run(test())


class TestShardedStorage(unittest.TestCase):
    """Test ShardedStorage implementation."""

    def setUp(self):
        self.shards = [
            MemoryDistributedStorage(StorageConfig(cache_enabled=False))
            for _ in range(3)
        ]
        self.sharded = ShardedStorage(self.shards, replication_factor=2)

    def test_shard_selection(self):
        shard = self.sharded._get_shard("test_key")

        self.assertIn(shard, self.shards)

    def test_consistent_hashing(self):
        shard1 = self.sharded._get_shard("key1")
        shard2 = self.sharded._get_shard("key1")

        self.assertIs(shard1, shard2)

    def test_replication(self):
        shards = self.sharded._get_shards_for_key("test_key")

        self.assertEqual(len(shards), 2)
        self.assertNotEqual(shards[0], shards[1])

    def test_put_get(self):
        async def test():
            result = await self.sharded.put("key1", "value1")

            self.assertTrue(result)

            value = await self.sharded.get("key1")

            self.assertEqual(value, "value1")

        asyncio.run(test())

    def test_delete(self):
        async def test():
            await self.sharded.put("key1", "value1")

            result = await self.sharded.delete("key1")

            self.assertTrue(result)

            value = await self.sharded.get("key1")
            self.assertIsNone(value)

        asyncio.run(test())

    def test_get_stats(self):
        async def test():
            stats = await self.sharded.get_stats()

            self.assertEqual(stats["backend"], "sharded")
            self.assertEqual(stats["shard_count"], 3)
            self.assertEqual(stats["replication_factor"], 2)
            self.assertEqual(len(stats["shards"]), 3)

        asyncio.run(test())


class TestStorageWithCache(unittest.TestCase):
    """Test storage with cache layer."""

    def setUp(self):
        self.config = StorageConfig(
            backend="memory",
            cache_enabled=True,
            cache_max_size=100,
            cache_ttl=60
        )
        self.storage = MemoryDistributedStorage(self.config)

    def test_cache_hit(self):
        async def test():
            await self.storage.put("key1", "value1")

            await self.storage.get("key1")

            stats = self.storage.get_cache_stats()

            self.assertEqual(stats["hits"], 1)

        asyncio.run(test())

    def test_cache_invalidation_on_delete(self):
        async def test():
            await self.storage.put("key1", "value1")
            await self.storage.get("key1")

            await self.storage.delete("key1")

            result = self.storage._cache.get("key1")
            self.assertIsNone(result)

        asyncio.run(test())


class TestFactoryFunction(unittest.TestCase):
    """Test create_distributed_storage factory function."""

    def test_create_memory_storage(self):
        storage = create_distributed_storage("memory")

        self.assertIsInstance(storage, MemoryDistributedStorage)

    def test_create_with_config(self):
        config = StorageConfig(ttl=3600)
        storage = create_distributed_storage("memory", config=config)

        self.assertEqual(storage.config.ttl, 3600)

    def test_unknown_backend(self):
        with self.assertRaises(ValueError):
            create_distributed_storage("unknown")


class TestIntegration(unittest.TestCase):
    """Integration tests for distributed storage."""

    def test_full_workflow(self):
        async def test():
            storage = create_distributed_storage("memory")

            await storage.put("config:api_key", "secret123")
            await storage.put("config:endpoint", "https://api.example.com")

            api_key = await storage.get("config:api_key")
            endpoint = await storage.get("config:endpoint")

            self.assertEqual(api_key, "secret123")
            self.assertEqual(endpoint, "https://api.example.com")

            keys = await storage.keys("config:*")
            self.assertEqual(len(keys), 2)

            await storage.delete("config:api_key")

            result = await storage.get("config:api_key")
            self.assertIsNone(result)

        asyncio.run(test())

    def test_concurrent_access(self):
        async def test():
            storage = create_distributed_storage("memory")

            async def writer(key_prefix, count):
                for i in range(count):
                    await storage.put(f"{key_prefix}:{i}", f"value{i}")

            async def reader(key_prefix, count):
                for i in range(count):
                    await storage.get(f"{key_prefix}:{i}")

            await asyncio.gather(
                writer("key", 10),
                reader("key", 10),
            )

            stats = await storage.get_stats()
            self.assertEqual(stats["total_keys"], 10)

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main(verbosity=2)
