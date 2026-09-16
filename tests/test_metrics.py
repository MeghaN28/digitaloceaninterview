from app.core.metrics import Metrics, timed


def test_metrics_snapshot_computes_percentiles():
    m = Metrics()
    for value in [10, 20, 30, 40, 100]:
        m.record("op", value)

    snap = m.snapshot()["op"]

    assert snap["count"] == 5
    assert snap["errors"] == 0
    assert snap["p50_ms"] == 30
    assert snap["max_ms"] == 100


def test_metrics_tracks_errors():
    m = Metrics()
    m.record("op", 5, is_error=False)
    m.record("op", 5, is_error=True)

    assert m.snapshot()["op"]["errors"] == 1


def test_timed_records_duration_and_reraises():
    m = Metrics()

    try:
        with timed(m, "op"):
            raise ValueError("boom")
    except ValueError:
        pass

    snap = m.snapshot()["op"]
    assert snap["count"] == 1
    assert snap["errors"] == 1


def test_metrics_endpoint_reports_http_and_db_sections(client):
    client.get("/v1/images/does-not-exist")

    resp = client.get("/metrics")

    assert resp.status_code == 200
    body = resp.json()
    assert "http" in body
    assert "db" in body
    assert "GET /v1/images/{image_id}" in body["http"]
    assert body["http"]["GET /v1/images/{image_id}"]["count"] >= 1
