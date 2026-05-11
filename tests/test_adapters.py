import tempfile
import unittest
from pathlib import Path

from app.adapters.object_storage import LocalObjectStorage
from app.adapters.vector_store import HashEmbeddingProvider, InMemoryVectorStore, _cosine


class AdapterTests(unittest.TestCase):
    def test_local_object_storage_puts_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.txt"
            source.write_text("hello", encoding="utf-8")
            storage = LocalObjectStorage(str(Path(temp_dir) / "objects"))
            stored = Path(storage.put_file(source, "docs/source.txt"))
            self.assertTrue(stored.exists())
            self.assertEqual(stored.read_text(encoding="utf-8"), "hello")
            self.assertEqual(storage.delete_file("docs/source.txt"), 1)
            self.assertFalse(stored.exists())

    def test_local_object_storage_deletes_prefix_safely(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.txt"
            source.write_text("hello", encoding="utf-8")
            storage = LocalObjectStorage(str(Path(temp_dir) / "objects"))
            storage.put_file(source, "projects/proj_1/a.txt")
            storage.put_file(source, "projects/proj_1/nested/b.txt")
            storage.put_file(source, "projects/proj_2/c.txt")
            self.assertEqual(storage.delete_prefix("projects/proj_1"), 2)
            self.assertEqual(storage.delete_prefix("../outside"), 0)
            self.assertTrue((Path(temp_dir) / "objects" / "projects" / "proj_2" / "c.txt").exists())

    def test_local_object_storage_rejects_traversal_on_put(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.txt"
            source.write_text("hello", encoding="utf-8")
            storage = LocalObjectStorage(str(Path(temp_dir) / "objects"))
            with self.assertRaises(ValueError):
                storage.put_file(source, "../outside.txt")
            self.assertFalse((Path(temp_dir) / "outside.txt").exists())

    def test_in_memory_vector_store_searches_terms(self):
        store = InMemoryVectorStore()
        store.upsert_text("materials", "mat_1", "核心交换机 包转发率 800Mpps", {"page": 3})
        hits = store.search("materials", "交换机 800Mpps")
        self.assertEqual(hits[0].id, "mat_1")
        self.assertEqual(hits[0].payload["page"], 3)
        self.assertEqual(store.search("materials", "completely-unrelated"), [])
        store.delete_text("materials", "mat_1")
        self.assertEqual(store.search("materials", "交换机 800Mpps"), [])

    def test_hash_embedding_and_cosine_are_stable(self):
        embedding = HashEmbeddingProvider()
        first = embedding.embed("same text")
        second = embedding.embed("same text")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertAlmostEqual(_cosine([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertEqual(_cosine([1.0, 0.0], [0.0, 1.0]), 0.0)


if __name__ == "__main__":
    unittest.main()
