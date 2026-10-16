
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rate_limit():
    # Use a valid JWT belonging to a test user.
    token = "YOUR_VALID_TEST_JWT"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    results = []

    for i in range(15):
        response = client.post(
            "/shorten",
            json={
                "long_url": f"https://example.com/page/{i}"
            },
            headers=headers
        )

        results.append(response.status_code)

    # First 10 requests should succeed.
    assert results[:10] == [201] * 10

    # Last 5 requests should be rejected.
    assert results[10:] == [429] * 5

