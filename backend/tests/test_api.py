def make(client, auth, url="https://example.com/a", **extra):
    return client.post("/api/links", json={"original_url": url, **extra}, headers=auth)


def test_register_login_and_duplicate(client, auth):
    r = client.post("/api/auth/register", json={
        "name": "X", "email": "T@example.com", "password": "password123", "confirm_password": "password123"})
    assert r.status_code == 409  # email is case-insensitive
    r = client.post("/api/auth/login", json={"email": "t@example.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "t@example.com"


def test_login_lockout(client, auth):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "t@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "t@example.com", "password": "password123"}).status_code == 429


def test_shorten_redirect_and_stats(client, auth):
    link = make(client, auth).json()
    r = client.get(f"/{link['code']}", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "https://example.com/a"
    client.get(f"/{link['code']}", follow_redirects=False)  # second hit comes from cache, must still count
    stats = client.get(f"/api/stats/{link['code']}", headers=auth).json()
    assert stats["total_clicks"] == 2
    assert sum(d["clicks"] for d in stats["clicks_per_day"]) == 2


def test_custom_code_and_conflict(client, auth):
    assert make(client, auth, custom_code="my-link").json()["code"] == "my-link"
    assert make(client, auth, url="https://other.com", custom_code="my-link").status_code == 409
    assert make(client, auth, custom_code="api").status_code == 422  # reserved word


def test_same_url_twice_is_allowed(client, auth):
    assert make(client, auth).status_code == 201
    assert make(client, auth).status_code == 201


def test_expired_and_disabled(client, auth):
    old = make(client, auth, expires_at="2020-01-01T00:00:00Z").json()
    assert client.get(f"/{old['code']}", follow_redirects=False).status_code == 410
    link = make(client, auth, url="https://b.com").json()
    client.patch(f"/api/links/{link['code']}", json={"is_active": False}, headers=auth)
    assert client.get(f"/{link['code']}", follow_redirects=False).status_code == 404


def test_cannot_touch_other_users_links(client, auth):
    link = make(client, auth).json()
    other = client.post("/api/auth/register", json={
        "name": "O", "email": "o@example.com", "password": "password123", "confirm_password": "password123"})
    h = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/api/stats/{link['code']}", headers=h).status_code == 403
    assert client.delete(f"/api/links/{link['code']}", headers=h).status_code == 403


def test_rate_limit(client, auth):
    codes = [make(client, auth, url=f"https://example.com/{i}").status_code for i in range(13)]
    assert codes[:10] == [201] * 10 and codes[10:] == [429] * 3


def test_requires_auth(client):
    assert client.post("/api/links", json={"original_url": "https://x.com"}).status_code == 401
