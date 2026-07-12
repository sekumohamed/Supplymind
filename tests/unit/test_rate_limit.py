import time
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.utils import rate_limit as rl


def make_request(ip="1.2.3.4", forwarded_for=None, internal_key=None):
    """Build a minimal fake Request with just what enforce_rate_limit reads."""
    headers = {}
    if forwarded_for is not None:
        headers["x-forwarded-for"] = forwarded_for
    if internal_key is not None:
        headers["x-internal-key"] = internal_key

    req = MagicMock()
    req.headers = headers
    req.client = MagicMock()
    req.client.host = ip
    return req


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Module-level dict persists across tests unless we clear it each time."""
    rl._request_log.clear()
    yield
    rl._request_log.clear()


class TestBasicLimiting:
    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        req = make_request(ip="1.1.1.1")
        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)  # should never raise

    @pytest.mark.asyncio
    async def test_blocks_request_over_limit(self):
        req = make_request(ip="2.2.2.2")
        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)

        with pytest.raises(HTTPException) as exc_info:
            await rl.enforce_rate_limit(req)

        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_different_ips_tracked_independently(self):
        req_a = make_request(ip="3.3.3.1")
        req_b = make_request(ip="3.3.3.2")

        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req_a)

        # req_a is now exhausted, but req_b should be untouched
        await rl.enforce_rate_limit(req_b)  # should not raise

        with pytest.raises(HTTPException):
            await rl.enforce_rate_limit(req_a)


class TestClientIpResolution:
    @pytest.mark.asyncio
    async def test_uses_x_forwarded_for_when_present(self):
        req = make_request(ip="10.0.0.1", forwarded_for="9.9.9.9, 10.0.0.1")
        await rl.enforce_rate_limit(req)
        assert "9.9.9.9" in rl._request_log
        assert "10.0.0.1" not in rl._request_log

    @pytest.mark.asyncio
    async def test_falls_back_to_client_host_without_forwarded_header(self):
        req = make_request(ip="8.8.8.8")
        await rl.enforce_rate_limit(req)
        assert "8.8.8.8" in rl._request_log

    @pytest.mark.asyncio
    async def test_falls_back_to_unknown_when_no_client_info(self):
        req = MagicMock()
        req.headers = {}
        req.client = None
        await rl.enforce_rate_limit(req)
        assert "unknown" in rl._request_log


class TestWindowExpiry:
    @pytest.mark.asyncio
    async def test_old_requests_age_out_of_window(self, monkeypatch):
        fake_now = [1_000_000.0]
        monkeypatch.setattr(rl.time, "time", lambda: fake_now[0])

        req = make_request(ip="5.5.5.5")
        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)

        # confirm it's exhausted at this point in time
        with pytest.raises(HTTPException):
            await rl.enforce_rate_limit(req)

        # jump time forward past the window
        fake_now[0] += rl.WINDOW_SECONDS + 1

        await rl.enforce_rate_limit(req)  # should succeed again, window reset


class TestInternalKeyBypass:
    @pytest.mark.asyncio
    async def test_correct_internal_key_bypasses_limit_entirely(self, monkeypatch):
        monkeypatch.setattr(rl.settings, "internal_api_key", "secret123")
        req = make_request(ip="6.6.6.6", internal_key="secret123")

        # far more than MAX_REQUESTS_PER_WINDOW, should never raise
        for _ in range(rl.MAX_REQUESTS_PER_WINDOW * 3):
            await rl.enforce_rate_limit(req)

        # bypassed calls should not even be recorded in the log
        assert "6.6.6.6" not in rl._request_log

    @pytest.mark.asyncio
    async def test_wrong_internal_key_does_not_bypass(self, monkeypatch):
        monkeypatch.setattr(rl.settings, "internal_api_key", "secret123")
        req = make_request(ip="7.7.7.7", internal_key="wrong-key")

        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)

        with pytest.raises(HTTPException):
            await rl.enforce_rate_limit(req)

    @pytest.mark.asyncio
    async def test_missing_internal_key_header_does_not_bypass(self, monkeypatch):
        monkeypatch.setattr(rl.settings, "internal_api_key", "secret123")
        req = make_request(ip="7.7.7.8")  # no internal_key passed at all

        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)

        with pytest.raises(HTTPException):
            await rl.enforce_rate_limit(req)

    @pytest.mark.asyncio
    async def test_bypass_disabled_when_no_internal_key_configured(self, monkeypatch):
        monkeypatch.setattr(rl.settings, "internal_api_key", "")
        req = make_request(ip="7.7.7.9", internal_key="anything")

        for _ in range(rl.MAX_REQUESTS_PER_WINDOW):
            await rl.enforce_rate_limit(req)

        # since internal_api_key is falsy, the header should be ignored entirely
        with pytest.raises(HTTPException):
            await rl.enforce_rate_limit(req)