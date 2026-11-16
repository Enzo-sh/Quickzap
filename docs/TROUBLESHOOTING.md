# Solución de problemas

Antes de nada, dos comandos que dicen casi todo (y que conviene pegar al reportar un problema):

```bash
python -m quickzap hardware     # CPU, RAM, GPU y modelo recomendado
python -m quickzap doctor       # verifica Ollama, modelo, carga, generación y GPU
```

`doctor` separa los errores en **instalación**, **carga del modelo** y **generación**: empezá por la fase que falla.

## La página no abre / «No module named quickzap»

- Ejecutá los comandos **dentro de la carpeta del proyecto** (donde está `README.md`). Si descomprimiste un ZIP, a veces hay una carpeta dentro de otra.
- En Windows, lo más simple es el doble clic en `Iniciar-Quickzap.bat`.
- «No se pudo usar el puerto 8765»: ya hay otra copia abierta. Cerrala o usá `python -m quickzap --port 8766`.
- Abrí `http://localhost:8765` a mano si el navegador no se abrió solo.

## «Ollama no está activo» / «No se pudo conectar con Ollama»

- Abrí la aplicación **Ollama** (menú Inicio) o ejecutá `ollama serve`. El asistente (⇩) tiene el botón **Iniciar Ollama**.
- Comprobá que responde: abrí `http://127.0.0.1:11434` (debe decir «Ollama is running»).
- Si lo configuraste en otra dirección, Quickzap respeta la variable de entorno `OLLAMA_HOST`.
- Logs de Ollama — Windows: `%LOCALAPPDATA%\Ollama\server.log`; macOS: `~/.ollama/logs/server.log`; Linux: `journalctl -u ollama`.

## No se puede instalar Ollama desde el asistente

- **Windows:** el asistente usa `winget`; si no existe, descarga el instalador oficial. Aceptá el permiso de Windows cuando aparezca. Si un antivirus lo bloquea, instalá Ollama a mano desde <https://ollama.com/download> y tocá **Volver a comprobar**.
- `winget` no existe en versiones antiguas de Windows 10: instalá «Instalador de aplicación» desde Microsoft Store, o usá el instalador manual.
- **Linux:** el instalador oficial requiere `sudo`, así que el asistente solo muestra el comando: `curl -fsSL https://ollama.com/install.sh | sh`.

## La descarga del modelo falla o se corta

- «**Se cortó la conexión**»: revisá tu Internet y tocá **Reintentar descarga**. Ollama continúa desde donde quedó.
- «**No hay espacio suficiente**»: liberá disco. Los modelos se guardan en `C:\Users\<tu-usuario>\.ollama\models` (Windows) o `~/.ollama/models`; podés moverlos con la variable `OLLAMA_MODELS`.
- «**No encontré ese modelo**»: revisá el nombre. Las variantes Q5/Q8 usan etiquetas como `qwen2.5:7b-instruct-q5_K_M`; si alguna no existe en la biblioteca de Ollama, elegí otra cuantización y avisanos.

## «El modelo no entra en la memoria de tu equipo»

1. Elegí un modelo más chico o la cuantización **Q4** (asistente → ⇩).
2. Cerrá programas pesados (navegadores con muchas pestañas, juegos).
3. Reducí el contexto: por defecto son 4096 tokens. Todavía no hay un control en la interfaz; se cambia por la API local:
   ```powershell
   Invoke-RestMethod -Method Post -Uri http://localhost:8765/api/settings -ContentType application/json -Body '{"num_ctx": 2048}'
   ```
   y para liberar memoria cuando no lo usás: `-Body '{"keep_alive": "1m"}'` (por defecto, el modelo queda cargado 10 minutos).

## Va muy lento / «corre solo en CPU»

- Mirá el paso **Prueba** del asistente o el panel ▦: indica qué porcentaje del modelo está en la GPU. Con `ollama ps` también se ve (columna *PROCESSOR*).
- Con una GPU NVIDIA: actualizá los controladores y comprobá `nvidia-smi`. Si el modelo es más grande que la VRAM libre, parte va a la RAM y se vuelve más lento: probá un modelo más chico o Q4.
- Sin GPU compatible, la CPU es la opción: preferí modelos de 1.5B–3B. En AMD/Intel Quickzap no detecta la GPU (no la usa para recomendar), aunque Ollama podría aprovecharla.
- Ejecutá `python -m quickzap bench` y compartí el informe: ayuda a mejorar las recomendaciones.

## La velocidad es irregular

La prueba de estabilidad marca «irregular» si la ventana más lenta rinde menos del 70% de la mediana. Suele pasar por throttling térmico, modo de ahorro de energía o programas en segundo plano. Probá con el equipo enchufado y repetí.

## Sin Internet

El chat con el modelo local funciona sin conexión. Sin Internet no se pueden descargar modelos ni instalar Ollama. El indicador superior muestra «sin conexión».

## Borrar datos / empezar de cero

Cerrá Quickzap y borrá la carpeta `data/` (contiene `quickzap.db`: conversaciones, ajustes, métricas y benchmarks). Los modelos de Ollama no se tocan.

## Reportar un problema

Abrí un *issue* con: sistema operativo, salida de `python -m quickzap hardware` y `python -m quickzap doctor`, y qué esperabas que pasara. No pegues datos personales.
