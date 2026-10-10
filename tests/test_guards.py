"""The guards on POST /: token, required params, host allowlist.

Offline. The browser is never launched: start_browser is replaced with a
no-op, and for the happy path the browser handle is a fake whose page
reports a failed request carrying a code, which is how the real redirect
to the app scheme ends.
"""
import os
import sys
import types

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "stellantis_worker"))

try:
    import playwright.async_api  # noqa: F401
except ImportError:  # the guards need no Playwright
    sys.modules["playwright"] = types.ModuleType("playwright")
    sys.modules["playwright.async_api"] = types.ModuleType("playwright.async_api")
    sys.modules["playwright.async_api"].async_playwright = None

import main  # noqa: E402

ALLOWED_URL = "https://idpcvs.peugeot.com/am/oauth2/authorize?client_id=x&response_type=code"
BODY = {"url": ALLOWED_URL, "email": "morgan@example.com", "password": "hunter2"}


class FakeRequest:
    url = "mymap://oauth2redirect?code=FAKECODE&state=1"


class FakePage:
    def __init__(self):
        self.handlers = {}

    def on(self, event, handler):
        self.handlers[event] = handler

    async def goto(self, *args, **kwargs):
        pass

    async def wait_for_selector(self, *args, **kwargs):
        pass

    async def wait_for_load_state(self, *args, **kwargs):
        pass

    async def type(self, *args, **kwargs):
        pass

    async def click(self, selector, **kwargs):
        if "cvs_from" in selector:  # the authorize button: the redirect fails, carrying the code
            await self.handlers["requestfailed"](FakeRequest())


class FakeContext:
    async def new_page(self):
        return FakePage()

    async def close(self):
        pass


class FakeBrowser:
    def __init__(self):
        self.context_kwargs = None

    async def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        return FakeContext()

    async def close(self):
        pass


async def _no_browser():
    pass


@pytest.fixture
def fake_browser(monkeypatch):
    fake = FakeBrowser()
    monkeypatch.setattr(main, "browser", fake)
    return fake


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "start_browser", _no_browser)
    monkeypatch.setattr(main, "options", {"allowed_hosts": list(main.DEFAULT_ALLOWED_HOSTS), "token": ""})
    with TestClient(main.app) as c:
        yield c


def test_missing_params_is_400(client, fake_browser):
    r = client.post("/", json={"url": ALLOWED_URL, "email": "morgan@example.com"})
    assert r.status_code == 400
    assert "Missing required params" in r.json()["message"]
    assert fake_browser.context_kwargs is None


@pytest.mark.parametrize("url", [
    "http://idpcvs.peugeot.com/am/oauth2/authorize",   # not https
    "https://example.com/am/oauth2/authorize",
    "https://evilidpcvs.peugeot.com/",                 # suffix, not a label boundary
    "https://idpcvs.peugeot.com.example.net/",
    "https://morgan:hunter2@example.com@idpcvs.peugeot.com/",
    "file:///etc/passwd",
    "not a url",
])
def test_disallowed_host_is_400_before_the_browser(client, fake_browser, url):
    r = client.post("/", json=dict(BODY, url=url))
    assert r.status_code == 400
    assert "not allowed" in r.json()["message"]
    assert fake_browser.context_kwargs is None


def test_token_mismatch_is_401(client, fake_browser):
    main.options["token"] = "s3cret"
    assert client.post("/", json=BODY).status_code == 401
    assert client.post("/", json=BODY, headers={"X-Worker-Token": "wrong"}).status_code == 401
    assert fake_browser.context_kwargs is None
    # The right token gets through to the next guard.
    r = client.post("/", json={"url": ALLOWED_URL}, headers={"X-Worker-Token": "s3cret"})
    assert r.status_code == 400
    assert "Missing required params" in r.json()["message"]


def test_allowed_host_returns_the_code(client, fake_browser):
    r = client.post("/", json=BODY)
    assert r.status_code == 200
    assert r.json() == {"code": "FAKECODE"}
    # S1: certificate errors fail the login, and CSP is left alone.
    assert fake_browser.context_kwargs["ignore_https_errors"] is False
    assert "bypass_csp" not in fake_browser.context_kwargs


def test_allowlist_option_and_subdomains(client, fake_browser):
    main.options["allowed_hosts"] = ["example.test"]
    assert client.post("/", json=dict(BODY, url="https://sso.example.test/login")).status_code == 200
    assert client.post("/", json=BODY).status_code == 400


def test_debug_does_not_persist_between_requests(client, fake_browser, capsys):
    client.post("/", json=dict(BODY, debug=True))
    assert "Navigating to login" in capsys.readouterr().out
    client.post("/", json=BODY)
    assert "Navigating to login" not in capsys.readouterr().out
