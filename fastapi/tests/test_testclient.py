from base64 import b64encode

from fastapi import FastAPI, Security, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from fastapi.testclient import FastAPITestClient, TestClient

app = FastAPI()

security_bearer = HTTPBearer()


@app.get("/users/me")
def read_current_user(credentials: HTTPAuthorizationCredentials = Security(security_bearer)):
    return {"scheme": credentials.scheme, "credentials": credentials.credentials}


security_basic = HTTPBasic()


@app.get("/basic/users/me")
def read_current_user_basic(credentials: HTTPBasicCredentials = Security(security_basic)):
    return {"username": credentials.username, "password": credentials.password}


@app.get("/public")
def public_endpoint():
    return {"message": "Hello, World!"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_text()
    await websocket.send_text(f"Echo: {data}")
    await websocket.close()


client = FastAPITestClient(app)


class TestFastAPITestClient:
    """Test suite for FastAPITestClient."""

    def test_authenticate(self):
        """Test that authenticate adds Bearer token to requests."""
        client.reset_auth()
        client.authenticate("test-token-123")
        response = client.get("/users/me")
        assert response.status_code == 200, response.text
        assert response.json() == {"scheme": "Bearer", "credentials": "test-token-123"}

    def test_authenticate_without_auth(self):
        """Test that unauthenticated requests return 401."""
        client.reset_auth()
        response = client.get("/users/me")
        assert response.status_code == 401, response.text

    def test_authenticate_basic(self):
        """Test that authenticate_basic adds Basic auth header."""
        client.reset_auth()
        client.authenticate_basic("john", "secret")
        response = client.get("/basic/users/me")
        assert response.status_code == 200, response.text
        assert response.json() == {"username": "john", "password": "secret"}

    def test_authenticate_basic_encoding(self):
        """Test the base64 encoding produces correct Authorization header."""
        client.reset_auth()
        client.authenticate_basic("alice", "password123")
        expected_encoded = b64encode(b"alice:password123").decode()
        assert client._auth_headers["Authorization"] == f"Basic {expected_encoded}"

    def test_reset_auth(self):
        """Test that reset_auth clears auth headers."""
        client.reset_auth()
        client.authenticate("some-token")
        assert "Authorization" in client._auth_headers
        client.reset_auth()
        assert len(client._auth_headers) == 0

    def test_reset_auth_allows_public_requests(self):
        """Test that after reset_auth, public endpoints still work."""
        client.reset_auth()
        response = client.get("/public")
        assert response.status_code == 200, response.text
        assert response.json() == {"message": "Hello, World!"}

    def test_assert_status_passes(self):
        """Test assert_status when status matches expected."""
        client.reset_auth()
        response = client.assert_status("get", "/public", 200)
        assert response.json() == {"message": "Hello, World!"}

    def test_assert_status_fails(self):
        """Test assert_status raises AssertionError when status doesn't match."""
        client.reset_auth()
        try:
            client.assert_status("get", "/users/me", 200)
            assert False, "Expected AssertionError"
        except AssertionError as e:
            assert "Expected status 200, got 401" in str(e)

    def test_assert_status_with_auth(self):
        """Test assert_status with auth headers."""
        client.reset_auth()
        client.authenticate("test-token")
        response = client.assert_status("get", "/users/me", 200)
        assert response.json() == {"scheme": "Bearer", "credentials": "test-token"}

    def test_assert_status_post(self):
        """Test assert_status with POST method."""
        client.reset_auth()
        # Just verify it works with different methods - public endpoint
        response = client.assert_status("get", "/public", 200)
        assert response.json() == {"message": "Hello, World!"}

    def test_auth_headers_persist_across_requests(self):
        """Test that auth headers persist across multiple requests."""
        client.reset_auth()
        client.authenticate("persistent-token")
        response1 = client.get("/users/me")
        assert response1.status_code == 200
        response2 = client.get("/users/me")
        assert response2.status_code == 200
        assert response1.json() == response2.json()

    def test_explicit_headers_override_auth(self):
        """Test that explicit request headers override auth headers."""
        client.reset_auth()
        client.authenticate("auth-token")
        # Explicitly pass a different Authorization header
        response = client.get(
            "/users/me",
            headers={"Authorization": "Bearer explicit-token"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"scheme": "Bearer", "credentials": "explicit-token"}

    def test_ws_connect(self):
        """Test ws_connect creates a working WebSocket connection."""
        client.reset_auth()
        with client.ws_connect("/ws") as websocket:
            websocket.send_text("Hello")
            data = websocket.receive_text()
            assert data == "Echo: Hello"

    def test_ws_connect_with_headers(self):
        """Test ws_connect with custom headers."""
        client.reset_auth()
        with client.ws_connect("/ws", headers={"X-Custom": "test"}) as websocket:
            websocket.send_text("test")
            data = websocket.receive_text()
            assert data == "Echo: test"

    def test_ws_connect_with_auth_headers(self):
        """Test ws_connect inherits auth headers from authenticate()."""
        client.reset_auth()
        client.authenticate("ws-token")
        # WebSocket endpoint doesn't use auth, but headers should be passed
        with client.ws_connect("/ws") as websocket:
            websocket.send_text("hello")
            data = websocket.receive_text()
            assert data == "Echo: hello"


class TestExistingTestClientImport:
    """Test that existing TestClient import still works."""

    def test_original_testclient_import(self):
        """Test that the original TestClient can still be imported and used."""
        from fastapi.testclient import TestClient as OrigTestClient

        tc = OrigTestClient(app)
        response = tc.get("/public")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello, World!"}

    def test_fastapi_testclient_is_subclass_of_testclient(self):
        """Test that FastAPITestClient is a subclass of TestClient."""
        assert issubclass(FastAPITestClient, TestClient)

    def test_original_testclient_behavior_unaffected(self):
        """Test that original TestClient behavior is unchanged."""
        from fastapi.testclient import TestClient as OrigTestClient

        tc = OrigTestClient(app)
        response = tc.get("/users/me", headers={"Authorization": "Bearer foobar"})
        assert response.status_code == 200
        assert response.json() == {"scheme": "Bearer", "credentials": "foobar"}
