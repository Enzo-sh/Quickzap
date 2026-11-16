# Modelos compatibles

Quickzap ofrece estos modelos de la [biblioteca de Ollama](https://ollama.com/library) en tres cuantizaciones. Esta tabla se **genera desde el
catálogo** (`python -m quickzap models --markdown`); una prueba comprueba que esté al día.

- **Q4** (`Q4_K_M`) es la variante por defecto de Ollama: la mejor relación calidad/velocidad/memoria. **Q5** usa ~15% más memoria y **Q8** ~75% más.
- La *memoria estimada* suma pesos + caché de contexto (4096 tokens) + buffers. Es una **estimación**, no una medición: se irá ajustando con los
  [benchmarks](BENCHMARKS.md).
- Quickzap clasifica cada variante según tu equipo (cabe en GPU / GPU + RAM / solo CPU / excede) y **no recomienda** las que no entran.
- Los modelos no están en este repositorio; se descargan desde Ollama. Licencias: [THIRD_PARTY.md](../THIRD_PARTY.md).

| Modelo | Parámetros | Descarga Q4 (por defecto) | Q5 | Q8 | Memoria estimada Q4 / Q5 / Q8 | Licencia | Nota |
|---|---|---|---|---|---|---|---|
| Qwen 2.5 · 0.5B | 0.5B | `qwen2.5:0.5b` ~0.3 GB | `qwen2.5:0.5b-instruct-q5_K_M` | `qwen2.5:0.5b-instruct-q8_0` | 0.9 / 1.0 / 1.2 GB | Apache-2.0 | Mínimo. Solo para equipos muy limitados; respuestas básicas. |
| Qwen 2.5 · 1.5B | 1.5B | `qwen2.5:1.5b` ~0.9 GB | `qwen2.5:1.5b-instruct-q5_K_M` | `qwen2.5:1.5b-instruct-q8_0` | 1.6 / 1.8 / 2.3 GB | Apache-2.0 | Muy liviano, para equipos modestos. |
| Qwen 2.5 · 3B | 3.1B | `qwen2.5:3b` ~1.9 GB | `qwen2.5:3b-instruct-q5_K_M` | `qwen2.5:3b-instruct-q8_0` | 2.7 / 3.0 / 4.1 GB | Qwen Research (revisar) | Rápido y correcto en español. Buena opción sin GPU potente. |
| Llama 3.2 · 3B | 3.2B | `llama3.2:3b` ~2.0 GB | `llama3.2:3b-instruct-q5_K_M` | `llama3.2:3b-instruct-q8_0` | 2.8 / 3.1 / 4.2 GB | Llama 3.2 Community | Alternativa liviana de Meta. |
| Qwen 2.5 · 7B | 7.6B | `qwen2.5:7b` ~4.7 GB | `qwen2.5:7b-instruct-q5_K_M` | `qwen2.5:7b-instruct-q8_0` | 5.7 / 6.5 / 9.2 GB | Apache-2.0 | Muy buen equilibrio calidad/velocidad. |
| Llama 3.1 · 8B | 8.0B | `llama3.1:8b` ~4.9 GB | `llama3.1:8b-instruct-q5_K_M` | `llama3.1:8b-instruct-q8_0` | 6.0 / 6.8 / 9.6 GB | Llama 3.1 Community | Alternativa de Meta, muy capaz en conversación. |
| Qwen 2.5 · 14B | 14.7B | `qwen2.5:14b` ~9.0 GB | `qwen2.5:14b-instruct-q5_K_M` | `qwen2.5:14b-instruct-q8_0` | 10.5 / 12.0 / 17.1 GB | Apache-2.0 | Más calidad; requiere GPU grande o bastante RAM. |


Para agregar un modelo, ver [CONTRIBUTING](../CONTRIBUTING.md#agregar-un-modelo-al-catálogo).
