"""Tests for ChromaDB VectorStore operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from curiopilot.storage.vector_store import VectorStore


@pytest.fixture
def vs(tmp_path: Path) -> VectorStore:
    store = VectorStore(tmp_path / "chroma")
    store.open()
    return store


class TestVectorStoreOpen:
    def test_creates_directory_and_collection(self, tmp_path: Path) -> None:
        chroma_dir = tmp_path / "chroma_new"
        store = VectorStore(chroma_dir)
        store.open()
        assert chroma_dir.exists()
        assert store.count() == 0


class TestVectorStoreAdd:
    def test_add_and_query(self, vs: VectorStore) -> None:
        vs.add(
            doc_id="doc1",
            embedding=[1.0, 0.0, 0.0],
            metadata={"title": "Test Doc 1"},
            document="content 1",
        )
        vs.add(
            doc_id="doc2",
            embedding=[0.0, 1.0, 0.0],
            metadata={"title": "Test Doc 2"},
            document="content 2",
        )

        results = vs.query_similar([1.0, 0.0, 0.0], k=2)
        assert len(results) == 2
        assert results[0]["id"] == "doc1"
        assert results[0]["similarity"] > results[1]["similarity"]

    def test_count_reflects_insertions(self, vs: VectorStore) -> None:
        assert vs.count() == 0
        vs.add("a", [1.0, 0.0], metadata={"title": "a"}, document="a")
        assert vs.count() == 1
        vs.add("b", [0.0, 1.0], metadata={"title": "b"}, document="b")
        assert vs.count() == 2


class TestQuerySimilar:
    def test_empty_store_returns_empty(self, vs: VectorStore) -> None:
        results = vs.query_similar([1.0, 0.0, 0.0])
        assert results == []

    def test_similarity_ordering(self, vs: VectorStore) -> None:
        vs.add("exact", [1.0, 0.0, 0.0], metadata={"title": "exact"})
        vs.add("different", [0.0, 0.0, 1.0], metadata={"title": "different"})

        results = vs.query_similar([1.0, 0.0, 0.0], k=2)
        assert results[0]["id"] == "exact"
        assert results[0]["similarity"] > results[1]["similarity"]


class TestUpsertBehavior:
    def test_same_id_overwrites(self, vs: VectorStore) -> None:
        vs.add("doc1", [1.0, 0.0], metadata={"version": "1"})
        assert vs.count() == 1

        vs.add("doc1", [0.0, 1.0], metadata={"version": "2"})
        assert vs.count() == 1

        results = vs.query_similar([0.0, 1.0], k=1)
        assert results[0]["id"] == "doc1"
        assert results[0]["metadata"]["version"] == "2"
