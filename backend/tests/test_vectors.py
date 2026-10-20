import numpy as np

from app.services.vectors import from_blob, to_blob


def test_round_trip_keeps_values_as_float32() -> None:
    vector = np.array([0.1, -2.5, 3.25], dtype=np.float64)

    restored = from_blob(to_blob(vector))

    assert restored.dtype == np.float32
    assert np.allclose(restored, vector)


def test_768_dimensions_take_3_kb() -> None:
    assert len(to_blob(np.zeros(768))) == 768 * 4
