# listenyourPDFs — Problema, solución y requisitos

> Versión 1.0 — requisitos funcionales y no funcionales definidos con el autor (2026-08-04).

**Naturaleza del proyecto: open source (MIT), personal-first.** No es un SaaS: es una
herramienta que resuelve el problema para su autor y que cualquiera puede self-hostear
con sus propias API keys (BYOK: bring your own keys). Sin pagos, sin planes, sin
telemetría. El éxito se mide en uso diario real y en comunidad, no en ingresos.

## 1. El problema

Leer un PDF denso (paper, libro técnico, informe, documentación) es lento y frágil:

1. **Requiere tiempo de silla.** Solo se puede leer sentado y concentrado. El tiempo de commute, gimnasio, paseos o tareas domésticas no cuenta para aprender.
2. **La lectura pasiva no fija conocimiento.** Sin recuperación activa (active recall) y repaso espaciado, a la semana se ha olvidado la mayor parte.
3. **Los PDFs son hostiles al audio.** Un TTS ingenuo lee cabeceras, pies de página, citas `[12]`, URLs, tablas y ecuaciones tal cual — inescuchable en documentos reales.
4. **No todo el PDF vale lo mismo.** El 20% contiene el 80% del valor, pero un lector lineal no lo distingue.
5. **Escuchar es unidireccional.** Con audio puro no puedes preguntar "¿qué significa esto?", "¿por qué?", "ponme un ejemplo".

## 2. Estado del arte (agosto 2026)

| Producto | Qué hace bien | Qué le falta |
|---|---|---|
| **Speechify** (~50M usuarios) | TTS multiplataforma, 200+ voces, hasta 4.5x | Lectura lineal pasiva; cero aprendizaje activo |
| **ElevenReader** | Mejor calidad de voz del mercado | Extracción de PDF floja en docs complejos; pasivo |
| **Listening.com** ($12.99/mes) | Especializado en papers: salta citas, términos científicos, tablas | Sin Q&A, sin quizzes, sin repaso espaciado; cerrado |
| **NotebookLM** | Podcast de 2 voces sobre tus fuentes, modo interactivo | Es un *resumen* con formato fijo, no el documento; inexactitudes |
| **Recall / RemNote / Knowt** | Quizzes y flashcards desde PDF, repaso espaciado | Sin audio; apps de estudio visual |

**El hueco:** nadie cierra el ciclo **escuchar → preguntar → ser preguntado → repasar** sobre el documento real. Además, ninguno es open source ni self-hosteable.

## 3. La solución

**Un tutor de audio para tus PDFs.** El servidor convierte cualquier PDF en audio limpio
que escuchas como un podcast desde el móvil; puedes dirigirlo ("léeme la sección 3",
"explícame este concepto") y preguntarle por voz; con el tiempo, se asegura de que lo
escuchado se retiene (recall + repaso espaciado).

El "10x": tiempo muerto convertido en estudio (2-3x) × priorización dirigida (2x) × retención real (2x sobre escucha pasiva).

## 4. Decisiones de producto y arquitectura (cerradas con el autor, 2026-08-04)

| # | Decisión | Elección | Motivo |
|---|---|---|---|
| D1 | Tipo de documentos | **Pipeline adaptativa**: detecta qué hay (citas, ecuaciones, capítulos, tablas) y se adapta; el usuario puede dirigir qué leer (sección / página / concepto) | El autor quiere flexibilidad total, no un vertical |
| D2 | Escenario principal | **Móvil en movimiento** (andar, gym, commute) con auriculares | Es donde se multiplica el tiempo de aprendizaje |
| D3 | Dispositivo del autor | **iPhone**, pero debe funcionar para todo el mundo | Chrome en iOS usa WebKit: mismas restricciones que Safari |
| D4 | Plataforma | **PWA universal primero; wrapper Capacitor para iOS solo si el audio en background falla** | Máxima adopción OSS, riesgo controlado |
| D5 | Interacción | **Voz push-to-talk en MVP**: botón → pausa → hablas (STT) → responde en audio → retoma. Q&A por texto incluido. Manos libres continuo: v2 | Cubre el 90% del valor en movimiento con coste contenido |
| D6 | TTS por defecto | **OpenAI o Gemini TTS** (~1€/paper). Kokoro local como 2ª integración (self-host 0€). ElevenLabs como opción premium BYOK | Equilibrio calidad/precio; arquitectura multi-proveedor |
| D7 | LLM por defecto | **Claude** (fidelidad al documento, español). Multi-proveedor desde el día 1 (OpenAI, Gemini, Ollama) | Anti-alucinación es requisito duro |
| D8 | Primer nivel de escucha | **Completo limpio ("modo podcast")**: el documento entero, bien leído. Recorrido guiado y Resumen después | El autor quiere usarlo como un podcast primero |
| D9 | Idioma | **Siempre idioma original del documento** (sin traducción en pipeline). El tutor responde en el idioma del usuario | Fidelidad y simplicidad |
| D10 | Stack | **Backend Python FastAPI + frontend Next.js PWA**, Docker Compose | Python donde brilla (PDF/IA/jobs), Next donde brilla el autor (UI) |
| D11 | Datos | **SQLite + archivos en disco** (PDFs y MP3s en carpetas). Vectores: sqlite-vec si hace falta | Cero fricción para MVP y adopción OSS; migrable a Postgres |
| D12 | Arquitectura de ejecución | **Servidor hace el trabajo pesado; el móvil solo sube PDFs y reproduce** | La generación (5-15 min/doc) no puede depender de un iPhone desbloqueado |
| D13 | Hosting personal | **VPS (Hetzner ~6-9€/mes) + Coolify/Dokploy** compartido con las demás apps del autor | Coste fijo multi-app, deploy automático desde GitHub |
| D14 | Recall / aprendizaje activo | **v1, junto al push-to-talk** (su forma natural es por voz). MVP = escuchar bien | Evitar construirlo dos veces |
| D15 | Presupuesto APIs | **10-20€/mes** para uso personal (~10-15 papers/mes con TTS API + Claude) | Marca el nivel de cacheo/optimización necesario |
| D16 | Feed RSS podcast | **Aparcado como contingencia**: solo se activa si el audio en background de la PWA falla en iOS (1-2 días, 0€) | El autor no lo ve necesario de partida |

## 5. Requisitos funcionales

Prioridad MoSCoW: **M** (must, MVP) / **S** (should, v1) / **C** (could, después).

### RF-1. Ingesta y comprensión del documento
- **RF-1.1 (M)** Subir PDF (drag & drop / selector, también desde móvil). Soportar PDFs nativos de texto.
- **RF-1.2 (M)** Pipeline **adaptativa**: detectar qué contiene el documento (secciones, citas, ecuaciones, tablas, capítulos, multicolumna) y aplicar la limpieza que corresponda — sin asumir un tipo fijo de documento.
- **RF-1.3 (M)** Extraer estructura navegable: título, índice de secciones/capítulos con su rango de páginas, orden de lectura correcto en multicolumna.
- **RF-1.4 (M)** Limpieza para audio: eliminar cabeceras/pies repetidos, números de página, citas inline (configurable), URLs; expandir abreviaturas y símbolos.
- **RF-1.5 (S)** Tablas y figuras: descripción hablada breve y fiel ("La tabla 2 compara X e Y; lo relevante es…").
- **RF-1.6 (S)** Ecuaciones: leerlas en lenguaje natural o saltarlas con resumen, según preferencia.
- **RF-1.7 (C)** OCR para PDFs escaneados.
- **RF-1.8 (C)** Otras fuentes: EPUB, URL de artículo, arXiv ID.

### RF-2. Escucha dirigida y niveles de zoom
- **RF-2.1 (M)** Nivel *Completo* ("modo podcast"): el documento entero, limpio, en audio. **Es el primer nivel que se construye.**
- **RF-2.2 (M)** **Navegación dirigida por el usuario**: "léeme la sección X", "la página N", "sáltate esta sección" — por UI (índice tocable) y, con push-to-talk, por voz.
- **RF-2.3 (S)** "Explícame el concepto Y": el tutor localiza el concepto en el documento y lo explica anclado al texto.
- **RF-2.4 (S)** Nivel *Recorrido guiado*: versión por sección estilo "profesor explicando el documento" (~20 min).
- **RF-2.5 (S)** Nivel *Resumen* (~5 min) para triaje.
- **RF-2.6 (S)** Cambiar de nivel en caliente sin perder la posición.

### RF-3. Reproducción
- **RF-3.1 (M)** Play/pausa, velocidad 0.75x–3x, saltar ±15s, saltar por sección.
- **RF-3.2 (M)** TTS natural, español e inglés como mínimo; el audio se genera en el idioma original del documento (D9).
- **RF-3.3 (M)** Audio en background con pantalla bloqueada + controles del sistema (Media Session API). **Prueba de fuego en iPhone la semana 1** (D4); si falla: Capacitor, y como parche inmediato el feed RSS (D16).
- **RF-3.4 (M)** Sincronización audio↔texto: al escuchar se resalta el párrafo actual; la posición se guarda.
- **RF-3.5 (S)** Descarga offline del audio generado.

### RF-4. Interacción con el tutor
- **RF-4.1 (M)** **Push-to-talk**: botón (pantalla) → el audio se pausa → hablas → STT (Whisper o equivalente) → el tutor responde en audio → retoma donde iba.
- **RF-4.2 (M)** Q&A por texto con la misma lógica.
- **RF-4.3 (M)** Respuestas ancladas al documento, con referencia a la sección; "no está en el documento" explícito — nunca inventar.
- **RF-4.4 (S)** Comandos de navegación por voz: "salta a resultados", "repite eso", "más despacio", "resume este capítulo".
- **RF-4.5 (C)** Conversación manos libres continua (API realtime); modo socrático/debate.

### RF-5. Aprendizaje activo y retención (v1, junto al push-to-talk — D14)
- **RF-5.1 (S)** Preguntas de recall al cerrar cada sección (1-3), respondidas por voz o texto, con corrección breve.
- **RF-5.2 (M)** Marcar momentos ("esto es oro" / "no lo entiendo") con un tap; queda guardado con timestamp + párrafo. *(Las marcas sí entran en MVP: son baratas y alimentan todo lo demás.)*
- **RF-5.3 (S)** Cola de repaso espaciado (FSRS): lo fallado/marcado se reprograma; cada sesión abre con 2-5 min de repaso en audio.
- **RF-5.4 (S)** Ficha final por documento (resumen + marcas + rendimiento) exportable en Markdown.
- **RF-5.5 (C)** Export a Obsidian/Anki.

### RF-6. Biblioteca y progreso
- **RF-6.1 (M)** Biblioteca con estado (sin empezar / en curso con % / terminado) y posición guardada, accesible desde móvil y PC.
- **RF-6.2 (S)** Estadísticas: tiempo escuchado, % acierto en recall, cola de repaso.
- **RF-6.3 (C)** Colecciones y búsqueda semántica en toda la biblioteca.

### RF-7. Plataforma y self-hosting
- **RF-7.1 (M)** PWA responsive instalable; caso de uso principal móvil + auriculares (D2-D4).
- **RF-7.2 (M)** BYOK: API keys por variables de entorno; nunca en el repo ni en el cliente.
- **RF-7.3 (M)** Despliegue en un comando (Docker Compose) + guía de self-hosting en README (VPS/Coolify como camino documentado — D13).
- **RF-7.4 (M)** Proveedores LLM/TTS/STT intercambiables tras interfaz común (D6-D7): Claude/OpenAI/Gemini/Ollama; OpenAI-o-Gemini TTS/Kokoro/ElevenLabs; Whisper API o local.
- **RF-7.5 (C)** Feed RSS privado con token (contingencia iOS — D16).
- **RF-7.6 (C)** Multiusuario con autenticación para instancias compartidas.
- **RF-7.7 (C)** Wrapper Capacitor iOS (activar solo si RF-3.3 falla en PWA).

## 6. Requisitos no funcionales

- **RNF-1 Latencia de arranque:** de subir un PDF de ~20 páginas a poder darle play, < 60s. El audio restante se genera por delante de la posición de escucha (streaming/chunks); un documento entero puede tardar 5-15 min en total y se procesa en el servidor sin que el móvil esté abierto (D12).
- **RNF-2 Coste:** presupuesto objetivo del autor 10-20€/mes (D15). Implicaciones: cachear todo audio generado (no re-sintetizar nunca lo mismo), TTS por chunks bajo demanda, modelos medianos para limpieza y grandes solo para Q&A/recall.
- **RNF-3 Fidelidad (anti-alucinación):** todo lo afirmado en niveles generados (guiado/resumen) y en respuestas del tutor debe ser trazable al documento; citar sección; "no está en el documento" explícito.
- **RNF-4 Privacidad:** los PDFs no salen del servidor del usuario salvo hacia las APIs de IA elegidas por él; borrado real al eliminar; feed RSS (si se activa) protegido por token.
- **RNF-5 Robustez móvil:** la reproducción sobrevive a pantalla bloqueada y cambios de red (D2); la posición se persiste en servidor cada pocos segundos.
- **RNF-6 Adopción OSS:** otra persona debe poder desplegarlo con sus keys siguiendo solo el README (criterio de éxito nº 2); sin dependencias de servicios propietarios no sustituibles.
- **RNF-7 Portabilidad de datos:** todo en SQLite + carpetas de archivos (D11); backup = copiar un directorio.

## 7. Alcance por fases

**MVP ("escuchar bien"):** RF-1.1–1.4, RF-2.1–2.2, RF-3.1–3.4, RF-4.1–4.3, RF-5.2, RF-6.1, RF-7.1–7.4. Push-to-talk incluido. Un usuario, sin auth.

**v1 ("aprender"):** recall por voz (RF-5.1, 5.3, 5.4), niveles guiado/resumen (RF-2.3–2.6), tablas/ecuaciones (RF-1.5–1.6), comandos de voz (RF-4.4), offline (RF-3.5), estadísticas (RF-6.2).

**v2+:** manos libres realtime, OCR, multiusuario, Capacitor/RSS si hacen falta, export Obsidian/Anki, búsqueda semántica global.

**Criterios de éxito del MVP:**
1. El autor termina un paper de 15 páginas íntegramente andando, con al menos 3 interacciones push-to-talk útiles, y lo prefiere a Speechify/Listening.com.
2. Otra persona despliega su instancia con sus keys siguiendo solo el README.
3. Coste real del mes ≤ 20€ con ~10 documentos.

## 8. Riesgos técnicos priorizados

1. **Audio background en iOS-PWA** (RF-3.3) — validar semana 1 con un spike mínimo (una página que reproduce un MP3 con Media Session en iPhone bloqueado). Plan B: Capacitor; parche: RSS.
2. **Calidad de extracción/limpieza de PDF variados** (RF-1.2) — evaluar PyMuPDF vs docling vs marker con 5 PDFs reales del autor antes de fijar la librería.
3. **Latencia percibida** (RNF-1) — diseño por chunks desde el día 1, no como optimización posterior.
4. **Coste TTS descontrolado** (RNF-2) — contador de gasto visible en la UI desde el MVP.

## 9. Siguiente paso

`docs/02-arquitectura.md`: diseño técnico del MVP — módulos del backend (ingesta, generación, tutor, biblioteca), contratos de la interfaz multi-proveedor, modelo de datos SQLite, API REST/SSE entre PWA y backend, y el spike de audio iOS de la semana 1.
