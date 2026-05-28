from starlette.testclient import TestClient as TestClient  # noqa
from starlette.testclient import WebSocketTestSession
import base64
from typing import Any, Optional

import httpx


class FastAPITestClient(TestClient):
    """Extended TestClient with auth helpers and WebSocket convenience methods.

    Usage:

        from fastapi.testclient import FastAPITestClient

        client = FastAPITestClient(app)
        client.authenticate("my-token")
        response = client.get("/protected-endpoint")

        client.reset_auth()
        client.authenticate_basic("user", "pass")
        response = client.get("/basic-auth-endpoint")

        with client.ws_connect("/ws") as ws:
            ws.send_text("hello")
            data = ws.receive_text()

        client.assert_status("get", "/", 200)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auth_headers: dict[str, str] = {}

    def authenticate(self, token: str) -> None:
        """Add Authorization Bearer header to all subsequent requests.

        Args:
            token: The bearer token string.
        """
        self._auth_headers["Authorization"] = f"Bearer {token}"

    def authenticate_basic(self, username: str, password: str) -> None:
        """Add HTTP Basic auth header to all subsequent requests.

        Args:
            username: The username for basic auth.
            password: The password for basic auth.
        """
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self._auth_headers["Authorization"] = f"Basic {encoded}"

    def request(  # type: ignore[override]
        self,
        method: str,
        url: httpx._types.URLTypes,
        *,
        content: httpx._types.RequestContent | None = None,
        data: Any = None,
        files: httpx._types.RequestFiles | None = None,
        json: Any = None,
        params: httpx._types.QueryParamTypes | None = None,
        headers: httpx._types.HeaderTypes | None = None,
        cookies: httpx._types.CookieTypes | None = None,
        auth: httpx._types.AuthTypes | httpx._client.UseClientDefault = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: bool | httpx._client.UseClientDefault = httpx._client.USE_CLIENT_DEFAULT,
        timeout: httpx._types.TimeoutTypes | httpx._client.UseClientDefault = httpx._client.USE_CLIENT_DEFAULT,
        extensions: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make a request, automatically including stored auth headers."""
        # Merge auth headers into the request headers.
        # Auth headers are applied first; explicit request headers can override.
        if self._auth_headers:
            merged = dict(self._auth_headers)
            if headers:
                merged.update(headers)
            headers = merged

        return super().request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def ws_connect(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> WebSocketTestSession:
        """Create WebSocket connection, automatically including stored auth headers.

        Args:
            url: The WebSocket URL path (e.g. '/ws').
            headers: Additional headers to include.
            **kwargs: Additional arguments passed to websocket_connect.

        Returns:
            A WebSocketTestSession for the connection.
        """
        merged_headers = dict(self._auth_headers)
        if headers:
            merged_headers.update(headers)
        kwargs["headers"] = merged_headers
        return super().websocket_connect(url, **kwargs)

    def assert_status(
        self,
        method: str,
        url: str,
        expected_status: int,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a request and assert the response status code.

        Args:
            method: HTTP method (get, post, put, delete, etc.).
            url: Request URL.
            expected_status: Expected HTTP status code.
            **kwargs: Additional arguments passed to the request method.

        Returns:
            The response object.

        Raises:
            AssertionError: If the status code does not match expected_status.
        """
        response = getattr(self, method.lower())(url, **kwargs)
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}"
        )
        return response

    def reset_auth(self) -> None:
        """Clear all stored auth headers."""
        self._auth_headers.clear()
