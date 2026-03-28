"""FAISS Flat index wrapper with thread-safe add/search and persistence.

Uses a threading.Lock around write operations to prevent index corruption
from concurrent requests. The id_map (FAISS index position → cache key)
is persisted alongside the FAISS index for crash recovery.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import faiss
import numpy as np
import structlog

logger = structlog.get_logger()


class VectorStore:
    """Thread-safe FAISS IndexFlatIP wrapper for semantic similarity search.

    Uses inner product (IP) on L2-normalized vectors, which is equivalent
    to cosine similarity. Scores range from 0 to 1.
    """

    def __init__(self, dimension: int, index_path: str = "./data/faiss.index") -> None:
        self._dimension = dimension
        self._index_path = index_path
        self._id_map_path = index_path + ".idmap"
        self._lock = threading.Lock()
        self._id_map: list[str] = []

        # Load existing index and id_map, or create new
        if os.path.exists(index_path):
            logger.info("vector_store.loading", path=index_path)
            self._index = faiss.read_index(index_path)
            self._id_map = self._load_id_map()
            logger.info("vector_store.loaded", num_vectors=self._index.ntotal, id_map_size=len(self._id_map))
        else:
            logger.info("vector_store.creating", dimension=dimension)
            self._index = faiss.IndexFlatIP(dimension)

    def _load_id_map(self) -> list[str]:
        """Load the id_map from disk."""
        if os.path.exists(self._id_map_path):
            with open(self._id_map_path) as f:
                return json.load(f)
        return []

    def _save_id_map(self) -> None:
        """Save the id_map to disk."""
        Path(self._id_map_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._id_map_path, "w") as f:
            json.dump(self._id_map, f)

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
        """Save the FAISS index and id_map to disk."""
        Path(self._index_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            faiss.write_index(self._index, self._index_path)
            self._save_id_map()
            logger.info("vector_store.persisted", path=self._index_path, num_vectors=self._index.ntotal)

    def reset(self) -> None:
        """Clear the index (useful for testing)."""
        with self._lock:
            self._index.reset()
            self._id_map.clear()

    def flush(self) -> int:
        """Clear the index and remove the persisted id_map file.

        Returns the number of vectors that were cleared.
        """
        with self._lock:
            count = self._index.ntotal
            self._index.reset()
            self._id_map.clear()
            if os.path.exists(self._id_map_path):
                os.remove(self._id_map_path)
            logger.info("vector_store.flushed", vectors_cleared=count)
            return count

    def remove_by_key(self, key: str) -> bool:
        """Remove a single vector by its cache key.

        Returns True if the key was found and removed, False otherwise.
        Uses FAISS ``remove_ids`` with the id-map index.
        """
        with self._lock:
            if key not in self._id_map:
                return False
            idx = self._id_map.index(key)
            ids_to_remove = np.array([idx], dtype=np.int64)
            self._index.remove_ids(ids_to_remove)
            self._id_map.pop(idx)
            logger.debug("vector_store.removed", cache_key=key)
            return True

