# Compatible models

QuickZap offers these models from the [Ollama library](https://ollama.com/library) in three quantizations. This table is **generated from the
catalog** (`python -m quickzap models --markdown`); a test checks that it is up to date.

- **Q4** (`Q4_K_M`) is Ollama's default variant: the best balance of quality/speed/memory. **Q5** uses ~15% more memory and **Q8** ~75% more.
- *Estimated memory* adds weights + context cache (4096 tokens) + buffers. It is an **estimate**, not a measurement: it will be refined with the
  [benchmarks](BENCHMARKS.md).
- QuickZap classifies each variant for your computer (fits in GPU / GPU + RAM / CPU only / exceeds) and **does not recommend** those that do not fit.
- The models are not in this repository; they are downloaded from Ollama. Licenses: [THIRD_PARTY.md](../THIRD_PARTY.md).

| Model | Parameters | Q4 download (default) | Q5 | Q8 | Estimated memory Q4 / Q5 / Q8 | License | Note |
|---|---|---|---|---|---|---|---|
| Qwen 2.5 · 0.5B | 0.5B | `qwen2.5:0.5b` ~0.3 GB | `qwen2.5:0.5b-instruct-q5_K_M` | `qwen2.5:0.5b-instruct-q8_0` | 0.9 / 1.0 / 1.2 GB | Apache-2.0 | Minimal. Only for very limited computers; basic answers. |
| Qwen 2.5 · 1.5B | 1.5B | `qwen2.5:1.5b` ~0.9 GB | `qwen2.5:1.5b-instruct-q5_K_M` | `qwen2.5:1.5b-instruct-q8_0` | 1.6 / 1.8 / 2.3 GB | Apache-2.0 | Very lightweight, for modest computers. |
| Qwen 2.5 · 3B | 3.1B | `qwen2.5:3b` ~1.9 GB | `qwen2.5:3b-instruct-q5_K_M` | `qwen2.5:3b-instruct-q8_0` | 2.7 / 3.0 / 4.1 GB | Qwen Research | Fast and accurate in Spanish. Good choice without a powerful GPU. |
| Llama 3.2 · 3B | 3.2B | `llama3.2:3b` ~2.0 GB | `llama3.2:3b-instruct-q5_K_M` | `llama3.2:3b-instruct-q8_0` | 2.8 / 3.1 / 4.2 GB | Llama 3.2 Community | Lightweight alternative from Meta. |
| Qwen 2.5 · 7B | 7.6B | `qwen2.5:7b` ~4.7 GB | `qwen2.5:7b-instruct-q5_K_M` | `qwen2.5:7b-instruct-q8_0` | 5.7 / 6.5 / 9.2 GB | Apache-2.0 | Very good quality/speed balance. |
| Llama 3.1 · 8B | 8.0B | `llama3.1:8b` ~4.9 GB | `llama3.1:8b-instruct-q5_K_M` | `llama3.1:8b-instruct-q8_0` | 6.0 / 6.8 / 9.6 GB | Llama 3.1 Community | Alternative from Meta, very capable in conversation. |
| Qwen 2.5 · 14B | 14.7B | `qwen2.5:14b` ~9.0 GB | `qwen2.5:14b-instruct-q5_K_M` | `qwen2.5:14b-instruct-q8_0` | 10.5 / 12.0 / 17.1 GB | Apache-2.0 | Higher quality; requires a large GPU or plenty of RAM. |


To add a model, see [CONTRIBUTING](../CONTRIBUTING.md#adding-a-model-to-the-catalog).
