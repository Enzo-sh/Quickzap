# Third-Party Components and Licenses

This document lists the third-party software, AI models, services, and other components used by QuickZap.

QuickZap's own source code is licensed under the MIT License. This license does not automatically apply to third-party components, AI models, or external services.

## 1. QuickZap

- **License:** MIT License
- **Copyright:** Copyright (c) 2026 QuickZap contributors
- **License file:** [LICENSE](LICENSE)

The MIT License applies to QuickZap's original source code and contributions, unless otherwise stated.

## 2. Python

- **Project:** Python
- **License:** Python Software Foundation License
- **Website:** https://www.python.org/
- **License information:** https://docs.python.org/3/license.html

QuickZap requires Python 3.9 or later. Python itself is distributed separately from QuickZap.

## 3. Ollama

- **Project:** Ollama
- **License:** MIT License
- **Repository:** https://github.com/ollama/ollama
- **License:** https://github.com/ollama/ollama/blob/main/LICENSE

Ollama is used as an external runtime to download and run AI models locally. It is not bundled with or redistributed by QuickZap.

## 4. SQLite

- **Project:** SQLite
- **License:** Public Domain
- **Website:** https://www.sqlite.org/

QuickZap uses Python's built-in `sqlite3` module for local database storage. SQLite is in the public domain.

## 5. Playwright

- **Project:** Playwright
- **License:** Apache License 2.0
- **Repository:** https://github.com/microsoft/playwright
- **License:** https://github.com/microsoft/playwright/blob/main/LICENSE

Playwright is used by certain development and end-to-end testing scripts. It is not required to run the main QuickZap application.

## 6. AI Models

QuickZap can work with the following models through Ollama. These models are downloaded separately by the user and are not included in this repository.

| Model | License |
|---|---|
| `qwen2.5:0.5b` | Apache License 2.0 |
| `qwen2.5:1.5b` | Apache License 2.0 |
| `qwen2.5:3b` | Qwen Research License |
| `qwen2.5:7b` | Apache License 2.0 |
| `qwen2.5:14b` | Apache License 2.0 |
| `llama3.2:3b` | Llama 3.2 Community License |
| `llama3.1:8b` | Llama 3.1 Community License |

### Qwen 2.5

- **Organization:** Alibaba Cloud
- **Model information:** https://qwenlm.github.io/blog/qwen2.5-llm/
- **Qwen 2.5 3B license:** https://huggingface.co/Qwen/Qwen2.5-3B/blob/main/LICENSE

The Qwen 2.5 3B model has a separate Qwen Research License. Do not assume it has the same terms as the Apache-licensed Qwen 2.5 models.

### Meta Llama

- **Organization:** Meta
- **Model information:** https://ai.meta.com/resources/models-and-libraries/llama-downloads/
- **Llama 3.2 license:** https://dev.meta.ai/llama/llama3_2/license
- **Llama 3.1 license and model information:** https://huggingface.co/meta-llama/Llama-3.1-8B/blob/main/README.md

Llama models are subject to their respective Meta Community License terms, which are different from the MIT License used by QuickZap.

Users are responsible for reviewing and complying with the applicable model licenses before downloading or using any model.

## 7. External Data Services

QuickZap can access the following external APIs for information retrieval. These services are accessed over HTTP and are not bundled with the application.

### Wikipedia

- **API:** https://es.wikipedia.org/w/api.php
- **API documentation:** https://www.mediawiki.org/wiki/API:Main_page
- **Content licensing:** Wikipedia text is generally available under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0), with some content potentially subject to different terms.
- **Copyright information:** https://en.wikipedia.org/wiki/Wikipedia:Copyrights

### Wikidata

- **API:** https://www.wikidata.org/w/api.php
- **Licensing:** CC0 1.0 Universal
- **Licensing information:** https://www.wikidata.org/wiki/Wikidata:Licensing

### OpenAlex

- **API:** https://api.openalex.org/works
- **Data licensing:** CC0
- **API documentation:** https://docs.openalex.org/
- **Transparency and licensing:** https://openalex.org/transparency

External services may have their own terms of use, rate limits, and attribution requirements. Users should consult the relevant service documentation.

## 8. Python Dependencies

QuickZap's main application code uses Python's standard library and does not require third-party Python packages for its core functionality.

Examples of standard-library modules used include:

- `urllib`
- `sqlite3`
- `json`
- `threading`
- `subprocess`
- `http.server`
- `pathlib`
- `platform`

The `requirements.txt` file does not currently list mandatory third-party runtime packages.

Playwright is used by selected testing scripts and is separate from the application's core runtime dependencies.

## 9. GitHub Actions

QuickZap uses the following third-party GitHub Actions in its continuous integration workflows.

### actions/checkout

- **Repository:** https://github.com/actions/checkout
- **License:** MIT License
- **Purpose:** Checks out the repository so workflows can access its source code.

### actions/setup-python

- **Repository:** https://github.com/actions/setup-python
- **License:** MIT License
- **Purpose:** Configures Python versions in CI environments.

These actions are used exclusively by GitHub Actions workflows. They are not runtime dependencies of QuickZap and are not bundled with the application.

## 10. License Separation and Disclaimer

QuickZap's MIT License applies only to the original QuickZap code and contributions covered by that license.

It does not grant additional rights to:

- Ollama or its software.
- Third-party AI models and their weights.
- External APIs or data retrieved from external services.
- Third-party development and testing tools.
- GitHub Actions or other external CI components.

Each third-party component remains subject to its own license, terms, and usage restrictions.

QuickZap is not affiliated with, endorsed by, or officially associated with Alibaba Cloud, Meta, Ollama, Wikipedia, Wikidata, OpenAlex, Microsoft, or GitHub.

Users are responsible for complying with the licenses and terms applicable to the third-party software, models, and services they choose to use.