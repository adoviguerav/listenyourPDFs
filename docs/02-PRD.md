# listenyourPDFs — PRD y fases de ejecución

> Versión 1.0 (2026-08-04). Requisitos y decisiones detalladas: `01-problema-y-solucion.md`.
> Arquitectura técnica: `03-arquitectura.md` (pendiente de cerrar con el autor).

## Producto en una frase

Tutor de audio open source y self-hosted para PDFs: el servidor convierte cualquier PDF
en audio limpio que escuchas como un podcast desde el móvil, puedes dirigirlo ("léeme la
sección 3") y preguntarle por voz, y más adelante se asegura de que lo escuchado se
retiene (recall + repaso espaciado).

## Usuarios

1. **El autor** (usuario 0): iPhone, escucha andando/gym, papers y documentos variados, presupuesto APIs 10-20€/mes.
2. **Self-hosters OSS**: despliegan su instancia con sus propias keys siguiendo el README.

## Criterios de éxito globales

1. El autor termina un paper de 15 páginas íntegramente andando, con ≥3 interacciones push-to-talk útiles, y lo prefiere a Speechify/Listening.com.
2. Otra persona despliega su instancia con sus keys siguiendo solo el README.
3. Coste real ≤ 20€/mes con ~10 documentos.

## Método de trabajo

Cada fase se ejecuta en bucle **planificar → implementar → testear** hasta cumplir su
Definition of Done (DoD). No se pasa a la fase siguiente con la DoD incompleta. Cada
fase termina con código pusheado, tests en verde y una demo utilizable.

---

## Fase 0 — Spikes de riesgo (≈1 semana)

**Objetivo:** matar los 3 riesgos técnicos antes de construir nada encima.

| Spike | Pregunta que responde | Salida |
|---|---|---|
| S0.1 Audio iOS | ¿Una PWA reproduce MP3 con pantalla bloqueada en el iPhone del autor (Media Session + `<audio>`)? | Veredicto GO/NO-GO → decide si se activa RSS (plan B) y/o Capacitor |
| S0.2 Extracción PDF | ¿Qué librería extrae mejor 5 PDFs reales del autor (paper 2-col, libro, informe con tablas, escaneado, slides)? | Librería elegida + calidad esperada por tipo de doc |
| S0.3 Voz TTS | ¿Qué voz/motor suena mejor en ES e EN a coste ≤1€/paper? (prueba con el mismo fragmento en OpenAI TTS, Gemini TTS, Kokoro) | Motor+voz por defecto |

**DoD:** los 3 veredictos documentados en `docs/spikes/` con evidencia (grabación de pantalla del iPhone, tabla comparativa de extracción, audios de muestra).

## Fase 1 — Pipeline núcleo: PDF → audio (≈2 semanas)

**Objetivo:** el corazón del producto. Un PDF entra, sale audio limpio escuchable, sin UI todavía (API + CLI).

**Alcance (RF):** RF-1.1–1.4 (ingesta adaptativa, estructura navegable, limpieza), RF-2.1 (nivel Completo), RF-3.2 (TTS ES/EN, idioma original), RNF-1 (play en <60s vía chunks), RNF-2 (cache de audio, contador de coste).

**Entregable:** `POST /documents` con un PDF → estado de procesamiento → lista de chunks de audio reproducibles por sección + estructura del documento en JSON.

**DoD:**
- Los 5 PDFs del spike S0.2 pasan por la pipeline y producen audio escuchable de principio a fin (verificado a oído por el autor).
- Tests automáticos: unitarios de limpieza (golden files: entrada PDF → texto limpio esperado), integración de la pipeline con un PDF fixture, contrato de la interfaz multi-proveedor (LLM/TTS mockeados).
- Ningún chunk se sintetiza dos veces (cache verificada por test).
- Contador de coste por documento registrado en BD.

## Fase 2 — Biblioteca + reproductor PWA (≈2 semanas)

**Objetivo:** escuchar de verdad desde el iPhone andando. El "modo podcast" completo.

**Alcance (RF):** RF-3.1 (controles, velocidad, saltos), RF-3.3 (background + Media Session; aplicar veredicto S0.1), RF-3.4 (sync audio↔texto, posición persistida), RF-2.2 (navegación dirigida por índice tocable), RF-5.2 (marcas), RF-6.1 (biblioteca con progreso), RF-7.1 (PWA instalable), RF-7.5 (QR onboarding).

**Entregable:** PWA instalada en el iPhone del autor; sube un PDF desde el móvil, y lo escucha entero con pantalla bloqueada.

**DoD:**
- El autor completa un paseo de 30 min escuchando un paper sin tocar el móvil salvo para marcar.
- La posición sobrevive a: bloquear pantalla, perder red, cerrar y reabrir la app.
- Tests: componentes del reproductor, E2E (Playwright) del flujo subir→procesar→escuchar→retomar, Lighthouse PWA installable.
- Si S0.1 fue NO-GO: feed RSS activado y verificado en Apple Podcasts (D16).

## Fase 3 — Tutor push-to-talk (≈2 semanas)

**Objetivo:** el diferencial. Preguntar hablando y ser respondido con fidelidad al documento.

**Alcance (RF):** RF-4.1 (push-to-talk: pausa→STT→respuesta en audio→retoma), RF-4.2 (Q&A texto), RF-4.3 (respuestas ancladas con cita de sección, "no está en el documento"), RNF-3 (anti-alucinación).

**Entregable:** durante la escucha, botón grande de hablar; pregunta por voz respondida en <10s con referencia a la sección.

**DoD:**
- 20 preguntas de prueba sobre un paper: ≥18 respondidas correctamente con cita, 0 respuestas inventadas (las 2 restantes deben ser "no está en el documento" o rechazo correcto).
- La reproducción retoma exactamente donde se pausó tras cada interacción.
- Tests: contrato STT mockeado, evaluación automatizada de anclaje (respuestas contienen referencia válida a sección existente), E2E del ciclo completo.

## Fase 4 — Release OSS v0.1 (≈1 semana)

**Objetivo:** que cualquiera pueda usarlo. Cierra el MVP.

**Alcance (RF):** RF-7.2 (BYOK env vars), RF-7.3 (Docker Compose un comando + guía self-host), RF-7.4 (proveedores intercambiables documentados), RNF-4 (privacidad), RNF-6 (adopción), despliegue real en el VPS del autor (Coolify), protección de la instancia expuesta a internet.

**DoD:**
- `docker compose up` desde cero en una máquina limpia deja la app funcionando.
- Una persona ajena despliega su instancia siguiendo solo el README (criterio de éxito nº 2).
- Instancia del autor corriendo en su VPS con HTTPS y protegida.
- README con: qué es, demo (GIF), instalación, configuración de proveedores, FAQ.
- Release v0.1 etiquetada en GitHub.

---

## v1 — "Aprender" (post-MVP, fases 5-7 orientativas)

- **Fase 5 — Recall y repaso:** RF-5.1 (preguntas por sección vía push-to-talk), RF-5.3 (cola FSRS, repaso en audio al abrir sesión), RF-5.4 (ficha Markdown por documento).
- **Fase 6 — Niveles de zoom:** RF-2.4 (Recorrido guiado), RF-2.5 (Resumen), RF-2.6 (cambio en caliente), RF-2.3 ("explícame el concepto Y").
- **Fase 7 — Escucha rica:** RF-1.5–1.6 (tablas/figuras/ecuaciones habladas), RF-4.4 (comandos de voz), RF-3.5 (offline), RF-6.2 (estadísticas).

## v2+ (backlog)

Manos libres realtime, OCR, multiusuario, Capacitor/APK (RF-7.8), export Obsidian/Anki, búsqueda semántica global, EPUB/arXiv.

## Fuera de alcance (todo el proyecto, salvo decisión nueva)

Monetización, telemetría, cuentas cloud propias, apps de store como canal principal, traducción automática de documentos (D9).
