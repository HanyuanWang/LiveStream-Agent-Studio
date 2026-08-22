from __future__ import annotations

import json
import http.client
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(method: str, url: str, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None, timeout: int = 60, max_attempts: int = 5) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(max_attempts):
        request = urllib.request.Request(url, data=payload, method=method, headers=headers or {})
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == max_attempts - 1:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.RemoteDisconnected) as exc:
            if attempt == max_attempts - 1:
                raise RuntimeError(f"网络请求失败，已重试 {max_attempts} 次: {exc}") from exc
        time.sleep(min(2**attempt, 8))
    raise RuntimeError("网络请求失败")
