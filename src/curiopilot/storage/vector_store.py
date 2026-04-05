"""ChromaDB-backed vector store for article embeddings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb

log = logging.getLogger(__name__)

COLLECTION_NAME = "article_embeddings"


class VectorStore:
    """Wraps a persistent ChromaDB collection for article similarity search."""

    def __init__(self, persist_dir: str | Path) -> None:
        self._persist_dir = str(persist_dir)
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def open(self) -> None:
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            "VectorStore opened at %s (%d existing documents)",
            self._persist_dir,
            self._collection.count(),
        )

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("VectorStore not opened; call open() first")
        return self._collection

    def count(self) -> int:
        return self.collection.count()

    def add(
        self,
        doc_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        document: str = "",
    ) -> None:
        self.collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            metadatas=[metadata or {}],
            documents=[document],
        )

    def query_similar(
        self,
        embedding: list[float],
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-k most similar documents with their distances.

        ChromaDB with cosine space returns *distances* where 0 = identical.
        We convert to a *similarity* in [0, 1] via ``similarity = 1 - distance``.
        """
        n_existing = self.collection.count()
        if n_existing == 0:
            return []

        actual_k = min(k, n_existing)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=actual_k,
            include=["distances", "metadatas", "documents"],
        )

        items: list[dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for i, doc_id in enumerate(ids):
            similarity = 1.0 - distances[i]
            items.append({
                "id": doc_id,
                "similarity": similarity,
                "metadata": metadatas[i] if metadatas else {},
                "document": documents[i] if documents else "",
            })

        return items

    def query_batch(
        self,
        embeddings: list[list[float]],
        k: int = 5,
    ) -> list[list[dict[str, Any]]]:
        """Query multiple embeddings in a single ChromaDB call."""
        n_existing = self.collection.count()
        if n_existing == 0:
            return [[] for _ in embeddings]

        actual_k = min(k, n_existing)
        results = self.collection.query(
            query_embeddings=embeddings,
            n_results=actual_k,
            include=["distances", "metadatas", "documents"],
        )

        all_items: list[list[dict[str, Any]]] = []
        for row_idx in range(len(embeddings)):
            ids = results.get("ids", [[]])[row_idx]
            distances = results.get("distances", [[]])[row_idx]
            metadatas = (results.get("metadatas") or [[]])[row_idx]
            documents = (results.get("documents") or [[]])[row_idx]
            items = []
            for i, doc_id in enumerate(ids):
                items.append({
                    "id": doc_id,
                    "similarity": 1.0 - distances[i],
                    "metadata": metadatas[i] if metadatas else {},
                    "document": documents[i] if documents else "",
                })
            all_items.append(items)
        return all_items

    def add_batch(
        self,
        doc_ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
        documents: list[str],
    ) -> None:
        """Upsert multiple embeddings in a single ChromaDB call."""
        # Guard: ChromaDB rejects duplicate IDs within a single upsert call
        seen_ids: dict[str, int] = {}
        for i, doc_id in enumerate(doc_ids):
            seen_ids[doc_id] = i
        if len(seen_ids) < len(doc_ids):
            keep = sorted(seen_ids.values())
            doc_ids = [doc_ids[i] for i in keep]
            embeddings = [embeddings[i] for i in keep]
            metadatas = [metadatas[i] for i in keep]
            documents = [documents[i] for i in keep]
        self.collection.upsert(
            ids=doc_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
