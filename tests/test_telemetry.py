# Phase 1 implementation
import pytest

from app.costs import estimate_cost
from app.telemetry import get_records, get_summary, init_db, write_record


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_DB_PATH", str(tmp_path / "test.db"))
    import app.telemetry as t
    t.DB_PATH = str(tmp_path / "test.db")
    init_db()


def make_record(request_id="req-1", cache_hit=False, model="gpt-4o",
                prompt_tokens=100, completion_tokens=50):
    return {
        "request_id": request_id,
        "timestamp": "2025-01-01T00:00:00",
        "model_requested": model,
        "model_used": model,
        "cache_hit": cache_hit,
        "similarity_score": 0.95,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": estimate_cost(model, prompt_tokens, completion_tokens),
        "latency_ms": 120.5,
        "compressed": False,
        "compression_ratio": 1.0,
    }


def test_write_and_read():
    for i in range(5):
        write_record(make_record(request_id=f"req-{i}"))
    records = get_records()
    assert len(records) == 5


def test_summary_cache_hit_rate():
    write_record(make_record("r1", cache_hit=True))
    write_record(make_record("r2", cache_hit=False))
    write_record(make_record("r3", cache_hit=True))
    summary = get_summary()
    assert summary["cache_hit_rate"] == pytest.approx(2 / 3, rel=0.01)


def test_cost_estimation_accuracy():
    cost = estimate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    # 1000 * 5/1M + 500 * 15/1M = 0.005 + 0.0075 = 0.0125
    assert cost == pytest.approx(0.0125, rel=0.01)


def test_duplicate_request_id_ignored():
    write_record(make_record("dup"))
    write_record(make_record("dup"))  # should be silently ignored (INSERT OR IGNORE)
    assert len(get_records()) == 1


def test_summary_total_requests():
    for i in range(3):
        write_record(make_record(request_id=f"req-{i}"))
    summary = get_summary()
    assert summary["total_requests"] == 3
