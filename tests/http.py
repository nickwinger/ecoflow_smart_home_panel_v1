"""Socket-free HTTP boundary fixture with streamed response bodies."""

import json
from collections import defaultdict, deque
from contextlib import AbstractContextManager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
from yarl import URL


class MockHTTP(AbstractContextManager):
    """Mock ClientSession.get while exercising all production response parsing."""

    def __init__(self):
        self.responses = deque()
        self.requests = defaultdict(list)
        self.patcher = patch.object(aiohttp.ClientSession, "get", side_effect=self.request)

    def __enter__(self):
        self.patcher.start()
        return self

    def __exit__(self, *args):
        self.patcher.stop()

    def get(self, url, *, payload=None, body=None, status=200, headers=None, exception=None):
        self.responses.append((url, payload, body, status, headers, exception))

    def request(self, url, **kwargs):
        full_url = str(URL(url).with_query(kwargs["params"]))
        self.requests[("GET", full_url)].append(SimpleNamespace(kwargs=kwargs))
        expected, payload, body, status, headers, exception = self.responses.popleft()
        assert full_url == expected
        if exception:
            raise exception
        raw = (body if body is not None else json.dumps(payload)).encode()

        async def chunks(size):
            for start in range(0, len(raw), size):
                yield raw[start : start + size]

        response = SimpleNamespace(
            status=status, headers=headers or {}, content=SimpleNamespace(iter_chunked=chunks)
        )
        context = AsyncMock()
        context.__aenter__.return_value = response
        return context
