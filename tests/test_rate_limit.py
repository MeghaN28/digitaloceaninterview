import app.main as main_module


def test_rate_limit_returns_429_once_exceeded(client, monkeypatch):
    monkeypatch.setattr(main_module.rate_limiter, "max_requests", 2)

    first = client.get("/v1/images/does-not-exist")
    second = client.get("/v1/images/does-not-exist")
    third = client.get("/v1/images/does-not-exist")

    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert third.json() == {"detail": "rate limit exceeded"}


def test_healthz_and_readyz_are_not_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main_module.rate_limiter, "max_requests", 1)

    for _ in range(5):
        resp = client.get("/healthz")
        assert resp.status_code == 200
