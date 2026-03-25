"""FAISS Flat index wrapper with thread-safe add/search and persistence.

Uses a threading.Lock around write operations to prevent index corruption
from concurrent requests.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import faiss
import numpy as np
import structlog

logger = structlog.get_logger()


class VectorStore:
    """Thread-safe FAISS Flat (L2) index for semantic similarity search.

    Stores normalized vectors so L2 distance maps directly to cosine distance:
      cosine_similarity = 1 - (L2_distance^2 / 2)
    """

    def __init__(self, dimension: int, index_path: str = "./data/faiss.index") -> None:
        self._dimension = dimension
        self._index_path = index_path
        self._lock = threading.Lock()
        self._id_map: list[str] = []  # maps internal FAISS index position → cache key

        # Load existing index or create a new one
        if os.path.exists(index_path):
            logger.info("vector_store.loading", path=index_path)
            self._index = faiss.read_index(index_path)
            logger.info("vector_store.loaded", num_vectors=self._index.ntotal)
        else:
            logger.info("vector_store.creating", dimension=dimension)
            self._index = faiss.IndexFlatIP(dimension)  # Inner product on normalized vectors = cosine sim

    @property
    def size(self) -> int:
        """Return the number of vectors in the index."""
        return self._index.ntotal

    def add(self, vector: np.ndarray, cache_key: str) -> None:
        """Add a single vector to the index with an associated cache key.

        Thread-safe via a write lock.
        """
        vector = vector.reshape(1, -1).astype(np.float32)
        with self._lock:
            self._id_map.append(cache_key)
            self._index.add(vector)
            logger.debug("vector_store.added", cache_key=cache_key, total=self._index.ntotal)

    def search(self, vector: np.ndarray, k: int = 1) -> list[tuple[str, float]]:
        """Search for the k nearest neighbors.

        Returns a list of (cache_key, similarity_score) tuples, sorted by
        descending similarity. Similarity is cosine similarity (0 to 1) since
        vectors are normalized and we use IndexFlatIP.
        """
        if self._index.ntotal == 0:
            return []

        vector = vector.reshape(1, -1).astype(np.float32)
        scores, indices = self._index.search(vector, min(k, self._index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            if idx < len(self._id_map):
                results.append((self._id_map[idx], float(score)))

        return results

    def persist(self) -> None:
        """Save the FAISS index to disk."""
        Path(self._index_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            faiss.write_index(self._index, self._index_path)
            logger.info("vector_store.persisted", path=self._index_path, num_vectors=self._index.ntotal)

    def reset(self) -> None:
        """Clear the index (useful for testing)."""
        with self._lock:
            self._index.reset()
            self._id_map.clear()
