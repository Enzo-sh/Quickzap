# Benchmarks

Quickzap no fija requisitos mínimos arbitrarios: las recomendaciones de [`hardware.py`](../quickzap/hardware.py) son **estimaciones**
y queremos reemplazarlas por **mediciones reales de computadoras distintas**. Este documento explica cómo medir y cómo aportar.

## Qué se mide

| Métrica | Cómo se obtiene |
|---|---|
| Tiempo de instalación | Lo registran `setup.ps1` / `setup.sh` en `data/install_timing.json` (si usaste el asistente, queda vacío) |
| Tiempo de inicialización | Importar el servidor + abrir la base + enlazar el puerto (`startup_ms`) |
| Modelo recomendado | Salida de la recomendación para ese hardware |
| Tiempo de carga | Se descarga el modelo y se vuelve a cargar, midiendo el tiempo real (en frío) |
| Tokens por segundo | `eval_count / eval_duration` que informa Ollama (excluye procesar el prompt) |
| Tiempo hasta el primer token | Desde que se envía la petición hasta el primer texto recibido (con el modelo ya cargado) |
| RAM y VRAM | Tamaño del modelo y reparto GPU/RAM según `/api/ps` de Ollama, más RAM y VRAM del sistema |
| Estabilidad | Generación de 128 tokens; velocidad por ventanas de 16 tokens. «Estable» = la ventana más lenta ≥ 70% de la mediana (umbral heurístico) |
| Calidad | 8 preguntas con respuesta verificable (aritmética, razonamiento, idioma, formato, instrucción, honestidad, no inventar). Es una prueba de humo, **no un benchmark académico** |
| Funcionamiento offline | El informe guarda si había Internet; con la red desconectada y `ok`, la columna «Sin Internet» dice *verificado* |

## Cómo ejecutarlo

1. Cerrá programas pesados y, si es un portátil, enchufalo.
2. Para evidenciar el funcionamiento offline, **desconectá Internet** (el modelo ya debe estar descargado).
3. Ejecutá, idealmente 2–3 veces, y quedate con la corrida más representativa:

```bash
python -m quickzap bench --quality
```

Genera `benchmarks/AAAA-MM-DD_<gpu-o-cpu>_<modelo>.json`. Es un archivo de texto: podés abrirlo para comprobar que no contiene datos
personales (incluye CPU, RAM, GPU, versión de Ollama y resultados; **no** incluye nombre de usuario ni de equipo).

## Comparar

```bash
python -m quickzap bench-compare "benchmarks/*.json"
```

Imprime una tabla Markdown (solo con informes correctos) con CPU, RAM, GPU, modelo, carga, primer token, tokens/s, VRAM/RAM del modelo,
estabilidad, calidad, instalación, inicio y verificación sin Internet.

## Cómo aportar

Enviá un *Pull Request* agregando tu JSON en `benchmarks/` (ver [CONTRIBUTING](../CONTRIBUTING.md)). Si algo salió mal, el informe también
sirve: los errores quedan separados en instalación, carga del modelo y generación (esos no entran en la tabla comparativa).

Con los datos reunidos se ajustarán las constantes de `hardware.py` (`RESERVE_VRAM_GB`, `RESERVE_RAM_GB`, `CPU_ONLY_MAX_PARAMS_B`,
bytes por parámetro) y se publicará una tabla de recomendaciones basada en evidencia.

## Resultados

Todavía no hay informes publicados. Esta sección se completará con la tabla de `bench-compare` cuando existan.
