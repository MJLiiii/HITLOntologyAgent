from fastapi.testclient import TestClient
from oe_studio.main import create_app
from oe_studio.settings import Settings


def test_actual_request_bytes_are_bounded_even_when_length_lies(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, max_upload_bytes=512))
    with TestClient(app) as client:
        response = client.post("/api/v1/projects", content=(b" " * 40000 for _ in range(3)),
                               headers={"Content-Length": "1", "Content-Type": "application/json"})
        assert response.status_code == 413


def test_malformed_declared_length_is_a_client_error(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/v1/projects", content=b"{}", headers={"Content-Length": "invalid"})
        assert response.status_code == 400
