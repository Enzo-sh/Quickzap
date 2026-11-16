"""Genera las capturas de docs/screenshots con un equipo de ejemplo y un Ollama SIMULADO (datos de demostración).
Para capturas con datos reales, corré la app en tu equipo y reemplazá los PNG.
Uso: python -m tests.screenshots"""
from pathlib import Path
from unittest import mock

from playwright.sync_api import sync_playwright

from quickzap import hardware
from tests.e2e_wizard import RTX3060, boot, stop

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    demo = {"snapshot": lambda: RTX3060, "ram": lambda: RTX3060["ram"], "cpu_info": lambda: RTX3060["cpu"],
            "vram_usage": lambda: {"used_mib": 5200, "total_mib": 8192}}     # equipo de ejemplo coherente en toda la interfaz
    patches = [mock.patch.object(hardware, name, fn) for name, fn in demo.items()]
    for patch in patches:
        patch.start()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tmp, fake, httpd, url = boot([])
        fake.token_delay = 0.004
        page = browser.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=1)
        page.goto(url)
        page.wait_for_selector("#wizard:not([hidden])")
        page.wait_for_selector(".model-option")
        page.screenshot(path=str(OUT / "wizard-model.png"))
        page.click("#wizard-next")
        page.wait_for_function("document.getElementById('wizard-body').textContent.includes('El modelo respondió')")
        page.click("text=Medir estabilidad")
        page.wait_for_function("document.getElementById('wizard-body').textContent.includes('Velocidad estable')")
        page.screenshot(path=str(OUT / "wizard-benchmark.png"))
        page.click("#wizard-next"); page.click("#wizard-next")
        page.fill("#chat-input", "Hola, ¿cómo estás?"); page.press("#chat-input", "Enter")
        page.wait_for_function("document.querySelector('.message-row.bot .message-note')?.textContent.includes('tokens/s')")
        page.click("#open-stats")
        page.wait_for_function("document.getElementById('stats-body').textContent.includes('tok/s')")
        page.screenshot(path=str(OUT / "stats.png"))
        stop(tmp, fake, httpd)
        browser.close()
    for patch in patches:
        patch.stop()
    print("capturas en", OUT)


if __name__ == "__main__":
    main()
