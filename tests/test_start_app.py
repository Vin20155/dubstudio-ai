import start_app
from types import SimpleNamespace


def test_main_disables_reload_for_frozen_executable(monkeypatch):
    run_options = {}
    monkeypatch.setattr(start_app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        start_app.threading,
        "Thread",
        lambda **kwargs: SimpleNamespace(start=lambda: None),
    )
    monkeypatch.setattr(
        start_app.uvicorn,
        "run",
        lambda app, **kwargs: run_options.update(kwargs),
    )

    start_app.main()

    assert run_options["reload"] is False


def test_main_keeps_reload_for_source_run(monkeypatch):
    run_options = {}
    monkeypatch.delattr(start_app.sys, "frozen", raising=False)
    monkeypatch.setattr(
        start_app.threading,
        "Thread",
        lambda **kwargs: SimpleNamespace(start=lambda: None),
    )
    monkeypatch.setattr(
        start_app.uvicorn,
        "run",
        lambda app, **kwargs: run_options.update(kwargs),
    )

    start_app.main()

    assert run_options["reload"] is True


def test_browser_opens_only_after_server_responds(monkeypatch):
    events = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(url, timeout):
        events.append(("request", url))
        if events.count(("request", url)) == 1:
            raise ConnectionRefusedError
        return Response()

    monkeypatch.setattr(start_app, "urlopen", fake_urlopen)
    monkeypatch.setattr(start_app.time, "monotonic", lambda: 0)
    monkeypatch.setattr(start_app.time, "sleep", lambda delay: events.append(("sleep", delay)))
    monkeypatch.setattr(
        start_app.webbrowser,
        "open",
        lambda url: events.append(("browser", url)) or True,
    )

    start_app._open_browser_when_ready()

    assert events == [
        ("request", "http://127.0.0.1:8000"),
        ("sleep", 0.5),
        ("request", "http://127.0.0.1:8000"),
        ("browser", "http://localhost:8000"),
    ]


def test_main_reuses_running_instance_instead_of_failing(monkeypatch):
    opened = []
    started = []
    monkeypatch.setattr(start_app, "_port_is_free", lambda port: port != 8000)
    monkeypatch.setattr(start_app, "_is_our_app", lambda port: port == 8000)
    monkeypatch.setattr(start_app.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(start_app.uvicorn, "run", lambda *a, **k: started.append((a, k)))

    start_app.main()

    assert opened == ["http://localhost:8000"]
    assert started == []


def test_main_uses_next_free_port_when_default_is_busy(monkeypatch):
    opened = []
    run_options = {}

    def fake_thread(**kwargs):
        return SimpleNamespace(start=lambda: None)

    monkeypatch.setattr(start_app, "_port_is_free", lambda port: port == 8001)
    monkeypatch.setattr(start_app, "_is_our_app", lambda port: False)
    monkeypatch.setattr(start_app.threading, "Thread", fake_thread)
    monkeypatch.setattr(start_app.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(start_app.uvicorn, "run", lambda app, **kwargs: run_options.update(kwargs))

    start_app.main()

    assert run_options["port"] == 8001

