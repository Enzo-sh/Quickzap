# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.2.0] - 2026-11-15

### Agregado
- Detección de CPU, RAM (total y disponible), GPU y VRAM; en Apple Silicon se estima la memoria unificada.
- Recomendación de modelo y cuantización (Q4/Q5/Q8) según los recursos; nunca se recomienda un modelo que no quepa. Modelos livianos (0.5B, 1.5B) para equipos modestos.
- Benchmark por fases: conexión, modelo, carga en frío, generación real, memoria, estabilidad; tokens/s y tiempo hasta el primer token.
- Errores clasificados en instalación / descarga / carga del modelo / generación, con sugerencias; reintento en cada etapa del asistente.
- Panel de estadísticas (▦) y comparación de modelos medidos.
- Métricas por respuesta (tokens/s, primer token, tiempo total) guardadas en SQLite.
- Comandos `hardware`, `bench`, `bench-compare` y `models`; batería de calidad de 8 preguntas (`bench --quality`).
- Ajuste `num_ctx` (4096 por defecto) para memoria predecible.
- Documentación de publicación: README, CONTRIBUTING, guía de problemas, modelos, benchmarks, licencias de terceros, escáner de secretos.

### Cambiado
- El estado de Internet se comprueba en segundo plano y nunca bloquea `/api/status` (antes podía tardar hasta 1,5 s sin conexión); se muestra «comprobando» mientras no se sabe.
- El paso «Prueba» del asistente usa el benchmark; se mantiene el mensaje «El modelo respondió: …».
- Si el puerto está ocupado se muestra un mensaje con la solución en lugar de un error técnico.

### Eliminado
- Endpoint `/api/setup/test` (reemplazado por `/api/benchmark`).

## [0.1.0] - 2026-11-14

### Agregado
- Chat local con Ollama, historial en SQLite, selector de modelo, descarga con progreso.
- Asistente de instalación (Ollama, modelo, prueba), `doctor`, instaladores `setup.ps1` / `setup.sh`, lanzador de doble clic.
- Protección contra peticiones de otros orígenes (Host/Origin).
