"""Browser test (optional): requires `pip install playwright` and `playwright install chromium`.
Usage: python -m tests.e2e_browser"""
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from quickzap import config, db, server
from tests.fake_ollama import FakeOllama


def main():
    tmp = tempfile.TemporaryDirectory()
    config.DATA_DIR = Path(tmp.name)
    fake = FakeOllama(["qwen2.5:7b"]).start()
    db.init()
    db.update_settings({"ollama_host": "http://127.0.0.1:%d" % fake.port, "model": "qwen2.5:7b"})
    httpd = server.make_server(port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = "http://localhost:%d/" % httpd.server_address[1]
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector("#model-select:not([hidden])")
        page.wait_for_function("document.getElementById('conn-text').textContent.includes('Ollama · qwen2.5:7b')")
        print("status:", page.inner_text("#conn-text"), "|", page.inner_text("#chat-status"))

        page.fill("#chat-input", "hello from the browser")
        page.press("#chat-input", "Enter")
        page.wait_for_function("document.querySelectorAll('.message-row.bot .bubble').length >= 1 "
                               "&& [...document.querySelectorAll('.message-row.bot .bubble')].pop().textContent.includes('Echo: hello from the browser')")
        bot = page.locator(".message-row.bot .bubble").last.inner_text()
        print("model reply:", bot.strip())
        assert bot.strip() == "Echo: hello from the browser", bot

        page.wait_for_function("document.querySelector('.message-row.bot .message-note').textContent.includes('tokens/s')")
        print("note:", page.locator(".message-row.bot .message-note").last.inner_text())

        page.reload()
        page.wait_for_function("document.querySelectorAll('.message-row').length === 2")
        print("after reload, messages restored:", page.locator(".message-row").count())

        page.click("#clear-chat")
        page.fill("#chat-input", "another conversation")
        page.press("#chat-input", "Enter")
        page.wait_for_selector(".message-row.bot .bubble")
        page.wait_for_function("document.querySelector('.message-row.bot .bubble').textContent.includes('Echo: another')")
        assert page.locator(".message-row").count() == 2

        page.screenshot(path="/tmp/quickzap_e2e.png", full_page=False)
        browser.close()

    _ = errors
    assert not errors, errors
    assert len(db.list_conversations()) == 2
    print("E2E OK: saved conversations =", len(db.list_conversations()))
    httpd.shutdown(); fake.stop(); tmp.cleanup()


if __name__ == "__main__":
    main()
