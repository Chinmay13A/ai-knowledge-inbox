"""Vector <-> SQLite BLOB conversion (float32, ~3 KB per 768-dim vector)."""

import numpy as np


def to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
