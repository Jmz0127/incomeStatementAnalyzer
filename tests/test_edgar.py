import pytest

from isviz.edgar import EdgarClient, EdgarError

TICKERS = {"0": {"cik_str": 1234567, "ticker": "FIX", "title": "Fixture Corp"}}


class FakeResponse:
    def __init__(self, status: int, payload: object = None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes, self.headers, self.calls = routes, {}, []

    def get(self, url, timeout):
        self.calls.append(url)
        for fragment, resp in self.routes.items():
            if fragment in url:
                return resp
        return FakeResponse(404)


def test_requires_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(EdgarError, match="User-Agent"):
        EdgarClient(cache_dir=None)


def test_lookup_and_facts(tmp_path, facts):
    session = FakeSession(
        {
            "company_tickers": FakeResponse(200, TICKERS),
            "CIK0001234567": FakeResponse(200, facts),
        }
    )
    client = EdgarClient("test test@example.com", cache_dir=tmp_path, session=session)
    assert session.headers["User-Agent"] == "test test@example.com"
    assert client.lookup("fix")["cik"] == 1234567
    assert client.company_facts("FIX")["entityName"] == "Fixture Corp"

    # Second client reads from the disk cache instead of the network.
    session2 = FakeSession({})
    client2 = EdgarClient("test test@example.com", cache_dir=tmp_path, session=session2)
    assert client2.company_facts("FIX")["entityName"] == "Fixture Corp"
    assert session2.calls == []


def test_unknown_ticker(tmp_path):
    session = FakeSession({"company_tickers": FakeResponse(200, TICKERS)})
    client = EdgarClient("t t@example.com", cache_dir=tmp_path, session=session)
    with pytest.raises(EdgarError, match="not found"):
        client.lookup("NOPE")


def test_http_errors(tmp_path):
    session = FakeSession(
        {
            "company_tickers": FakeResponse(200, TICKERS),
            "CIK0001234567": FakeResponse(503),
        }
    )
    client = EdgarClient("t t@example.com", cache_dir=tmp_path, session=session)
    with pytest.raises(EdgarError, match="503"):
        client.company_facts("FIX")


@pytest.mark.network
def test_live_apple():
    import os

    from isviz.statements import build_income_statement

    if not os.environ.get("SEC_USER_AGENT"):
        pytest.skip("SEC_USER_AGENT not set")
    client = EdgarClient(cache_dir=None)
    s = build_income_statement(client.company_facts("AAPL"), "AAPL", 5)
    assert s.company == "Apple Inc."
    assert s.data["revenue"].iloc[-1] > 300e9
