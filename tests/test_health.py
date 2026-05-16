import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_returns_ok(client: Client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "ok"
    assert data["db"] == "ok"
