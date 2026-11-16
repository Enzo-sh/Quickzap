# Contribuir a Quickzap

¡Gracias por querer ayudar! Quickzap busca ser una IA local rápida, fácil de instalar y útil también en computadoras modestas.

## Preparar el entorno

```bash
git clone https://github.com/<tu-usuario>/quickzap.git && cd quickzap
python -m unittest discover -s tests -t . -v      # no necesita dependencias ni GPU
python scripts/check_secrets.py                    # debe decir «Sin hallazgos.»
```

Las pruebas de navegador son opcionales: `pip install playwright && playwright install chromium && python -m tests.e2e_wizard`.

## Principios

- **Sin dependencias externas** en el código de la app (solo biblioteca estándar). Si una función de verdad las necesita, que sea opcional y documentada en `THIRD_PARTY.md`.
- **Nada de recursos remotos** en la interfaz (CDN, fuentes, scripts): Quickzap tiene que funcionar sin Internet.
- **No declares una función terminada si solo tiene interfaz.** Cada cambio lleva pruebas; los casos de error cuentan tanto como los felices.
- **Los números salen de mediciones**, no de suposiciones. Las reglas de `hardware.py` son heurísticas que queremos reemplazar con datos reales.
- Los mensajes para el usuario van en español, claros y con una sugerencia de qué hacer.

## Pull requests

1. Una idea por PR, con descripción de qué cambia y por qué.
2. `python -m unittest discover -s tests -t . -v` en verde y `python scripts/check_secrets.py` sin hallazgos.
3. Si cambia el comportamiento visible, actualizá `CHANGELOG.md` (sección *Sin publicar*) y la documentación.
4. Nunca incluyas claves, rutas personales ni datos de tus conversaciones.

## Agregar un modelo al catálogo

Editá `FAMILIES` en `quickzap/hardware.py` (nombre exacto de Ollama, parámetros reales, licencia) y regenerá la tabla:

```bash
python -m quickzap models --markdown   # pegá el resultado en docs/MODELS.md
```

Verificá que las etiquetas de cuantización (`<modelo>-instruct-q5_K_M`, `-q8_0`) existan en la biblioteca de Ollama: hay una prueba que
compara `docs/MODELS.md` con el catálogo.

## Aportar benchmarks

Los benchmarks reales de distintas computadoras son lo más valioso que podés aportar. Instrucciones y metodología en
[docs/BENCHMARKS.md](docs/BENCHMARKS.md): ejecutá `python -m quickzap bench --quality` y enviá el JSON de `benchmarks/` en un PR.
El informe no contiene datos personales (podés abrirlo y comprobarlo).

## Reportar un problema

Incluí la salida de `python -m quickzap hardware` y `python -m quickzap doctor`, y qué esperabas que pasara. Ver [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).
