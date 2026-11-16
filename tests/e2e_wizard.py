"""Pruebas de navegador del asistente y del panel de estadísticas (opcional; requiere playwright).
Uso: python -m tests.e2e_wizard"""
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

from playwright.sync_api import sync_playwright

from quickzap import config, db, hardware, installer, server
from tests.fake_ollama import FakeOllama

RTX3060 = {"os": "Windows 11", "cpu": {"name": "CPU de prueba", "threads": 12, "arch": "AMD64"},
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
    assert "Elegí tu modelo" in title(page), title(page)
    card7, card14 = page.locator(".model-option", has_text="Qwen 2.5 · 7B"), page.locator(".model-option", has_text="Qwen 2.5 · 14B")
    assert card7.locator("input").is_checked()
    assert "Recomendado" in card7.inner_text() and "Cabe en tu GPU" in card7.inner_text()
    assert "GPU + RAM (más lento)" in card14.inner_text()
    assert page.locator(".model-option", has_text="Qwen 2.5 · 0.5B").locator("select option").count() == 3
    print("tu equipo:", page.inner_text("#wizard-body p").splitlines()[0][:100])
    card7.locator("select").select_option(index=1)                      # Q5
    assert "(~5.4 GB)" in page.inner_text("#wizard-next"), page.inner_text("#wizard-next")
    card7.locator("select").select_option(index=0)                      # de vuelta a Q4
    assert "(~4.7 GB)" in page.inner_text("#wizard-next")

    fake.pull_delay = 0.25
    page.click("#wizard-next")
    page.wait_for_selector(".wizard-bar.indeterminate")
    page.wait_for_function("document.querySelector('.wizard-percent')?.textContent === '40%'")
    assert page.get_attribute(".wizard-bar", "aria-valuenow") == "40"
    assert "Descargando qwen2.5:7b" in page.inner_text(".wizard-progress-text")
    print("barra de descarga:", page.inner_text(".wizard-percent"), "|", page.inner_text(".wizard-progress-text"))
    page.wait_for_function("document.getElementById('wizard-title').textContent.startsWith('Probando')")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('El modelo respondió')")
    assert page.locator(".wizard-stages").count() == 1
    assert page.locator(".wizard-stages li.stage-ok").count() == 5, page.inner_text(".wizard-stages")
    for label in ("Velocidad", "Primer token", "Carga", "Memoria del modelo"):
        assert label.lower() in page.inner_text("#wizard-body").lower(), label
    print("informe:", page.inner_text("#wizard-body").replace("\n", " | ")[:260])
    fake.token_delay = 0.004
    page.click("text=Medir estabilidad")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('Velocidad estable')")
    print("estabilidad:", [t for t in page.inner_text("#wizard-body").splitlines() if "estable" in t][0])
    page.click("#wizard-next")
    assert "Todo listo" in title(page)
    page.click("#wizard-next")
    assert page.is_hidden("#wizard")
    page.fill("#chat-input", "hola"); page.press("#chat-input", "Enter")
    page.wait_for_function("[...document.querySelectorAll('.message-row.bot .bubble')].some(b => b.textContent.includes('Eco: hola'))")
    assert db.get_settings()["model"] == "qwen2.5:7b"
    assert not errors, errors
    page.close(); stop(tmp, fake, httpd)


def scenario_install_ollama(browser):
    tmp, fake, httpd, url = boot(["qwen2.5:7b"], down=True)
    state = {"installed": False, "attempt": 0}

    def fake_install():
        state["attempt"] += 1
        yield {"type": "log", "text": "Instalando Ollama con winget…"}
        if state["attempt"] == 1:
            raise installer.InstallError("Access is denied")           # primer intento: falla
        yield {"type": "progress", "percent": 25, "text": "Descargando Ollama · 200 MB de 800 MB"}
        time.sleep(0.5)
        yield {"type": "progress", "percent": 60, "text": "Descargando Ollama · 480 MB de 800 MB"}
        time.sleep(0.5)
        yield {"type": "progress", "percent": None, "text": "Instalando Ollama…"}
        time.sleep(0.4)
        state["installed"] = True
        yield {"type": "progress", "percent": 100, "text": "Ollama instalado"}
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
        assert "Motor de IA local" in title(page) and page.is_disabled("#wizard-next")
        page.click("text=Instalar Ollama")
        page.wait_for_selector(".wizard-error")                       # 1.er intento: error comprensible
        err = page.inner_text(".wizard-error")
        assert "Instalación: Faltan permisos" in err and "ollama.com/download" in err, err
        print("error de instalación:", err.replace("\n", " | "))
        page.click("text=Reintentar instalación")                     # reintento
        assert page.locator("#wizard-body button").first.is_disabled()   # no se puede pulsar dos veces
        assert page.locator(".wizard-error").count() == 0                # el error anterior se limpia al reintentar
        page.wait_for_function("document.querySelector('.wizard-percent')?.textContent === '60%'")
        assert "480 MB de 800 MB" in page.inner_text(".wizard-progress-text")
        page.wait_for_selector(".wizard-bar.indeterminate")
        page.wait_for_function("document.getElementById('wizard-body').textContent.includes('✓ Ollama está instalado y activo')")
        assert page.locator(".wizard-progress-block").count() == 0 and page.locator(".wizard-error").count() == 0
        page.click("#wizard-next")
        assert "Elegí tu modelo" in title(page)
        assert page.locator(".model-option", has_text="Qwen 2.5 · 7B").locator(".badge", has_text="Instalado").count() == 1
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
    page.click("#wizard-next")                                        # descarga que falla
    page.wait_for_selector(".wizard-error")
    err = page.inner_text(".wizard-error")
    assert "Descarga: No hay espacio suficiente en el disco" in err and "Liberá espacio" in err, err
    assert page.inner_text("#wizard-next") == "Reintentar descarga"
    print("error de descarga:", err.replace("\n", " | "))
    fake.pull_error = None
    page.click("#wizard-next")                                        # reintento correcto
    page.wait_for_function("document.getElementById('wizard-title').textContent.startsWith('Probando')")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('El modelo respondió')")
    page.click("#wizard-back")                                        # elegir otro modelo: se puede volver
    assert "Elegí tu modelo" in title(page)
    page.close()

    # error de carga en la prueba (memoria insuficiente) y reintento
    fake.fail_load = "model requires more system memory (10.0 GiB) than is available (6.0 GiB)"
    page = browser.new_page(); page.goto(url)
    page.wait_for_selector("#pull-model:not([hidden])")
    assert page.is_hidden("#wizard")                                  # todo está instalado: el asistente no se abre solo
    page.click("#pull-model")                                         # pero se puede reabrir cuando se quiera
    page.wait_for_selector("#wizard:not([hidden])")
    assert page.inner_text("#wizard-next") == "Usar este modelo"
    page.click("#wizard-next")                                        # ya está instalado: pasa directo a la prueba
    page.wait_for_selector(".wizard-error")
    err = page.inner_text(".wizard-error")
    assert "Carga del modelo: El modelo no entra en la memoria" in err, err
    assert page.locator(".wizard-stages li.stage-error").count() == 1 and page.is_disabled("#wizard-next")
    print("error de carga:", err.replace("\n", " | ")[:150])
    fake.fail_load = None
    page.click("text=Reintentar")
    page.wait_for_function("document.getElementById('wizard-body').textContent.includes('El modelo respondió')")
    assert not page.is_disabled("#wizard-next")
    page.close(); stop(tmp, fake, httpd)


def scenario_stats_panel(browser):
    tmp, fake, httpd, url = boot(["qwen2.5:7b"])
    page = browser.new_page(); errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url); page.wait_for_selector("#open-stats:not([hidden])")
    assert page.is_hidden("#wizard")
    page.fill("#chat-input", "hola"); page.press("#chat-input", "Enter")
    page.wait_for_function("document.querySelector('.message-row.bot .message-note')?.textContent.includes('primer token')")
    print("nota de la respuesta:", page.locator(".message-row.bot .message-note").last.inner_text())
    page.click("#open-stats")
    page.wait_for_function("document.getElementById('stats-body').textContent.includes('50 tok/s')")
    body = page.inner_text("#stats-body")
    for label in ("Modelo actual", "Ollama", "Conexión", "Velocidad", "Primer token", "Tiempo de respuesta", "RAM del sistema",
                  "VRAM (GPU)", "Memoria del modelo", "Conversaciones", "Espacio de datos"):
        assert label.lower() in body.lower(), label
    assert "100% en GPU" in body and "Activo" in body
    print("estadísticas:", body.replace("\n", " | ")[:300])
    assert "Comparación de modelos" not in body
    page.click("#stats-bench")
    page.wait_for_function("document.getElementById('stats-body').textContent.includes('Comparación de modelos')", timeout=15000)
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
