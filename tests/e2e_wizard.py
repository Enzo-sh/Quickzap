"""Browser tests for the wizard and the statistics panel (optional; requires playwright).
Usage: python -m tests.e2e_wizard"""
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

from playwright.sync_api import sync_playwright

from quickzap import config, db, hardware, installer, server
from tests.fake_ollama import FakeOllama

RTX3060 = {"os": "Windows 11", "cpu": {"name": "Test CPU", "threads": 12, "arch": "AMD64"},
           "ram": {"total_gb": 16.0, "available_gb": 10.0, "used_gb": 6.0}, "vram_mib": 8192, "unified": False,
           "gpus": [{"name": "NVIDIA GeForce RTX 3060", "vram_total_mib": 8192, "driver": None, "vendor": "nvidia", "estimated": False}]}


def boot(models, down=False):
    tmp = tempfile.TemporaryDirectory()
    config.DATA_DIR = Path(tmp.name)
    fake = FakeOllama(models).start()
    fake.down = down
    db.init()
    db.update_settings({"ollama_host": "http://127.0.0.1:%d" % fake.port, "model": "qwen2.5:7b"})
    httpd = server.make_server(port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return tmp, fake, httpd, "http://localhost:%d/" % httpd.server_address[1]


def stop(tmp, fake, httpd):
    httpd.shutdown(); fake.stop(); tmp.cleanup()


def title(page):
    return page.inner_text("#wizard-title")


def scenario_model_missing(browser):
    tmp, fake, httpd, url = boot([])
    page = browser.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_selector("#wizard:not([hidden])")
    assert "Choose your model" in title(page), title(page)
    card7, card14 = page.locator(".model-option", has_text="Qwen 2.5 · 7B"), page.locator(".model-option", has_text="Qwen 2.5 · 14B")
    assert card7.locator("input").is_checked()
    assert "Recommended" in card7.inner_text() and "Fits in your GPU" in card7.inner_text()
    assert "GPU + RAM (slower)" in card14.inner_text()
    assert page.locator(".model-option", has_text="Qwen 2.5 · 0.5B").locator("select option").count() == 3
    print("your computer:", page.inner_text("#wizard-body p").splitlines()[0][:100])
    card7.locator("select").select_option(index=1)                      # Q5
    assert "(~5.4 GB)" in page.inner_text("#wizard-next"), page.inner_text("#wizard-next")
    card7.locator("select").select_option(index=0)                      # de vuelta a Q4
    assert "(~4.7 GB)" in page.inner_text("#wizard-next")

    fake.pull_delay = 0.25
    page.click("#wizard-next")
    page.wait_for_selector(".wizard-bar.indeterminate")
    page.wait_for_function("document.querySelector('.wizard-percent')?.textContent === '40%'")
    assert page.get_attribute(".wizard-bar", "aria-valuenow") == "40"
    assert "Downloading qwen2.5:7b" in page.inner_text(".wizard-progress-text")
    print("download bar:", page.inner_text(".wizard-percent"), "|", page.inner_text(".wizard-progress-text"))
    page.wait_for_function("document.getElementById('wizard-title').textContent.startsWith('Testing')")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('The model replied')")
    assert page.locator(".wizard-stages").count() == 1
    assert page.locator(".wizard-stages li.stage-ok").count() == 5, page.inner_text(".wizard-stages")
    for label in ("Speed", "First token", "Load", "Model memory"):
        assert label.lower() in page.inner_text("#wizard-body").lower(), label
    print("report:", page.inner_text("#wizard-body").replace("\n", " | ")[:260])
    fake.token_delay = 0.004
    page.click("text=Measure stability")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('Stable speed')")
    print("stability:", [t for t in page.inner_text("#wizard-body").splitlines() if "stable" in t.lower()][0])
    page.click("#wizard-next")
    assert "All set" in title(page)
    page.click("#wizard-next")
    assert page.is_hidden("#wizard")
    page.fill("#chat-input", "hello"); page.press("#chat-input", "Enter")
    page.wait_for_function("[...document.querySelectorAll('.message-row.bot .bubble')].some(b => b.textContent.includes('Echo: hello'))")
    assert db.get_settings()["model"] == "qwen2.5:7b"
    assert not errors, errors
    page.close(); stop(tmp, fake, httpd)


def scenario_install_ollama(browser):
    tmp, fake, httpd, url = boot(["qwen2.5:7b"], down=True)
    state = {"installed": False, "attempt": 0}

    def fake_install():
        state["attempt"] += 1
        yield {"type": "log", "text": "Installing Ollama with winget…"}
        if state["attempt"] == 1:
            raise installer.InstallError("Access is denied")           # first attempt: fails
        yield {"type": "progress", "percent": 25, "text": "Downloading Ollama · 200 MB of 800 MB"}
        time.sleep(0.5)
        yield {"type": "progress", "percent": 60, "text": "Downloading Ollama · 480 MB of 800 MB"}
        time.sleep(0.5)
        yield {"type": "progress", "percent": None, "text": "Installing Ollama…"}
        time.sleep(0.4)
        state["installed"] = True
        yield {"type": "progress", "percent": 100, "text": "Ollama installed"}
        yield {"type": "done"}

    def fake_start(host, timeout=30):
        fake.down = False
        return {"ok": True}

    with mock.patch.object(installer, "find_ollama", lambda: "C:/ollama.exe" if state["installed"] else None), \
         mock.patch.object(installer, "can_auto_install", lambda: True), \
         mock.patch.object(installer, "install_ollama", fake_install), \
         mock.patch.object(installer, "start_ollama", fake_start):
        page = browser.new_page(); errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector("#wizard:not([hidden])")
        assert "Local AI engine" in title(page) and page.is_disabled("#wizard-next")
        page.click("text=Install Ollama")
        page.wait_for_selector(".wizard-error")                       # 1st attempt: understandable error
        err = page.inner_text(".wizard-error")
        assert "Installation: Missing permissions" in err and "ollama.com/download" in err, err
        print("installation error:", err.replace("\n", " | "))
        page.click("text=Retry installation")                        # retry
        assert page.locator("#wizard-body button").first.is_disabled()   # no se puede pulsar dos veces
        assert page.locator(".wizard-error").count() == 0                # the previous error is cleared on retry
        page.wait_for_function("document.querySelector('.wizard-percent')?.textContent === '60%'")
        assert "480 MB of 800 MB" in page.inner_text(".wizard-progress-text")
        page.wait_for_selector(".wizard-bar.indeterminate")
        page.wait_for_function("document.getElementById('wizard-body').textContent.includes('✓ Ollama is installed and running')")
        assert page.locator(".wizard-progress-block").count() == 0 and page.locator(".wizard-error").count() == 0
        page.click("#wizard-next")
        assert "Choose your model" in title(page)
        assert page.locator(".model-option", has_text="Qwen 2.5 · 7B").locator(".badge", has_text="Installed").count() == 1
        page.click("#wizard-skip")
        assert page.is_hidden("#wizard")
        page.wait_for_function("document.getElementById('conn-text').textContent.includes('Ollama · qwen2.5:7b')")
        page.click("#pull-model"); page.wait_for_selector("#wizard:not([hidden])")
        page.keyboard.press("Escape")
        assert page.is_hidden("#wizard")
        assert not errors, errors
        page.close()
    stop(tmp, fake, httpd)


def scenario_retry_after_failures(browser):
    tmp, fake, httpd, url = boot([])
    fake.pull_error = "write /models/blob: no space left on device"
    page = browser.new_page()
    page.goto(url); page.wait_for_selector("#wizard:not([hidden])")
    page.click("#wizard-next")                                        # download that fails
    page.wait_for_selector(".wizard-error")
    err = page.inner_text(".wizard-error")
    assert "Download: Not enough disk space" in err and "Free up space" in err, err
    assert page.inner_text("#wizard-next") == "Retry download"
    print("download error:", err.replace("\n", " | "))
    fake.pull_error = None
    page.click("#wizard-next")                                        # reintento correcto
    page.wait_for_function("document.getElementById('wizard-title').textContent.startsWith('Testing')")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('The model replied')")
    page.click("#wizard-back")                                        # choose another model: going back is allowed
    assert "Choose your model" in title(page)
    page.close()

    # load error in the test (out of memory) and retry
    fake.fail_load = "model requires more system memory (10.0 GiB) than is available (6.0 GiB)"
    page = browser.new_page(); page.goto(url)
    page.wait_for_selector("#pull-model:not([hidden])")
    assert page.is_hidden("#wizard")                                  # everything is installed: the wizard does not open by itself
    page.click("#pull-model")                                         # but it can be reopened at any time
    page.wait_for_selector("#wizard:not([hidden])")
    assert page.inner_text("#wizard-next") == "Use this model"
    page.click("#wizard-next")                                        # already installed: goes straight to the test
    page.wait_for_selector(".wizard-error")
    err = page.inner_text(".wizard-error")
    assert "Model load: The model does not fit in" in err, err
    assert page.locator(".wizard-stages li.stage-error").count() == 1 and page.is_disabled("#wizard-next")
    print("load error:", err.replace("\n", " | ")[:150])
    fake.fail_load = None
    page.click("text=Retry")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('The model replied')")
    assert not page.is_disabled("#wizard-next")
    page.close(); stop(tmp, fake, httpd)


def scenario_stats_panel(browser):
    tmp, fake, httpd, url = boot(["qwen2.5:7b"])
    page = browser.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url); page.wait_for_selector("#open-stats:not([hidden])")
    assert page.is_hidden("#wizard")
    page.fill("#chat-input", "hello"); page.press("#chat-input", "Enter")
    page.wait_for_function("document.querySelector('.message-row.bot .message-note')?.textContent.includes('first token')")
    print("reply note:", page.locator(".message-row.bot .message-note").last.inner_text())
    page.click("#open-stats")
    page.wait_for_function("document.getElementById('stats-body').textContent.includes('50 tok/s')")
    body = page.inner_text("#stats-body")
    for label in ("Current model", "Ollama", "Connection", "Speed", "First token", "Response time", "System RAM",
                  "VRAM (GPU)", "Model memory", "Conversations", "Data space"):
        assert label.lower() in body.lower(), label
    assert "100% on GPU" in body and "Running" in body
    print("statistics:", body.replace("\n", " | ")[:300])
    assert "Model comparison" not in body
    page.click("#stats-bench")
    page.wait_for_function("document.getElementById('stats-body').textContent.includes('Model comparison')", timeout=15000)
    assert "qwen2.5:7b — 50 tokens/s" in page.inner_text("#stats-body")
    page.keyboard.press("Escape")
    assert page.is_hidden("#stats")
    assert not errors, errors
    page.close(); stop(tmp, fake, httpd)


def main():
    with mock.patch.object(hardware, "snapshot", lambda: RTX3060), sync_playwright() as p:
        browser = p.chromium.launch()
        for scenario in (scenario_model_missing, scenario_install_ollama, scenario_retry_after_failures, scenario_stats_panel):
            scenario(browser)
            print("OK:", scenario.__name__)
        page = browser.new_page(viewport={"width": 390, "height": 800})
        tmp, fake, httpd, url = boot([])
        page.goto(url); page.wait_for_selector("#wizard:not([hidden])")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        stop(tmp, fake, httpd)
        browser.close()
    print("E2E WIZARD OK")


if __name__ == "__main__":
    main()
