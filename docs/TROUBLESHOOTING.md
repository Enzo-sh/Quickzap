# Troubleshooting

First, two commands that tell almost everything (and are worth pasting when reporting a problem):

```bash
python -m quickzap hardware     # CPU, RAM, GPU, and recommended model
python -m quickzap doctor       # checks Ollama, model, load, generation, and GPU
```

`doctor` separates errors into **installation**, **model load**, and **generation**: start with the failing phase.

## The page does not open / "No module named quickzap"

- Run the commands **inside the project folder** (where `README.md` is). If you unzipped a ZIP, sometimes there is a folder inside another.
- On Windows, the simplest option is to double-click `StartQuickzap.bat`.
- "Could not use port 8765": another copy is already open. Close it or use `python -m quickzap --port 8766`.
- Open `http://localhost:8765` manually if the browser did not open by itself.

## "Ollama is not running" / "Could not connect to Ollama"

- Open the **Ollama** app (Start menu) or run `ollama serve`. The wizard (⇩) has a **Start Ollama** button.
- Check that it responds: open `http://127.0.0.1:11434` (it should say "Ollama is running").
- If you configured a different address, QuickZap respects the `OLLAMA_HOST` environment variable.
- Ollama logs — Windows: `%LOCALAPPDATA%\Ollama\server.log`; macOS: `~/.ollama/logs/server.log`; Linux: `journalctl -u ollama`.

## Cannot install Ollama from the wizard

- **Windows:** the wizard uses `winget`; if it is unavailable, it downloads the official installer. Accept the Windows permission prompt when it appears. If an antivirus blocks it, install Ollama manually from <https://ollama.com/download> and click **Check again**.
- `winget` does not exist in older Windows 10 versions: install "App Installer" from the Microsoft Store, or use the manual installer.
- **Linux:** the official installer requires `sudo`, so the wizard only shows the command: `curl -fsSL https://ollama.com/install.sh | sh`.

## The model download fails or is interrupted

- "**The Internet connection was interrupted**": check your connection and click **Retry download**. Ollama resumes where it left off.
- "**Not enough disk space**": free up disk space. Models are stored in `C:\Users\<your-user>\.ollama\models` (Windows) or `~/.ollama/models`; you can move them with the `OLLAMA_MODELS` variable.
- "**Could not find that model**": check the name. Q5/Q8 variants use tags like `qwen2.5:7b-instruct-q5_K_M`; if one does not exist in the Ollama library, choose another quantization and let us know.

## "The model does not fit in your computer's memory"

1. Choose a smaller model or the **Q4** quantization (wizard → ⇩).
2. Close heavy programs (browsers with many tabs, games).
3. Reduce the context: the default is 4096 tokens. There is no control in the interface yet; change it through the local API:
   ```powershell
   Invoke-RestMethod -Method Post -Uri http://localhost:8765/api/settings -ContentType application/json -Body '{"num_ctx": 2048}'
   ```
   and to free memory when it is not in use: `-Body '{"keep_alive": "1m"}'` (by default, the model stays loaded for 10 minutes).

## Very slow / "runs on CPU only"

- Check the wizard's **Test** step or the ▦ panel: it shows what percentage of the model is on the GPU. `ollama ps` shows it too (*PROCESSOR* column).
- With an NVIDIA GPU: update the drivers and check `nvidia-smi`. If the model is larger than the free VRAM, part goes to RAM and becomes slower: try a smaller model or Q4.
- Without a compatible GPU, the CPU is the option: prefer 1.5B–3B models. On AMD/Intel, QuickZap does not detect the GPU (it does not use it for recommendations), although Ollama may be able to use it.
- Run `python -m quickzap bench` and share the report: it helps improve recommendations.

## Uneven speed

The stability test marks "uneven" if the slowest window performs below 70% of the median. This is usually due to thermal throttling, power-saving mode, or background programs. Try with the computer plugged in and repeat.

## Offline

Chatting with the local model works without a connection. Without Internet you cannot download models or install Ollama. The indicator at the top shows "offline".

## Clear data / start over

Close QuickZap and delete the `data/` folder (it contains `quickzap.db`: conversations, settings, metrics, and benchmarks). Ollama models are not touched.

## Reporting a problem

Open an *issue* with: operating system, output of `python -m quickzap hardware` and `python -m quickzap doctor`, and what you expected to happen. Do not paste personal data.
