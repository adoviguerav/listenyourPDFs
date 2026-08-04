# listenyourPDFs — Problema, solución y requisitos funcionales

> Versión 0.2 — documento de definición de producto. Vivo: se refina con cada decisión.

**Naturaleza del proyecto: open source (MIT), personal-first.** No es un SaaS: es una
herramienta que resuelve el problema para su autor y que cualquiera puede self-hostear
con sus propias API keys (BYOK: bring your own keys). Sin pagos, sin planes, sin
telemetría. El éxito se mide en uso diario real y en comunidad, no en ingresos.

## 1. El problema

Leer un PDF denso (paper, libro técnico, informe, documentación) es lento y frágil:

1. **Requiere tiempo de silla.** Solo se puede leer sentado y concentrado. El tiempo de commute, gimnasio, paseos o tareas domésticas no cuenta para aprender.
2. **La lectura pasiva no fija conocimiento.** Leer (u oír) de principio a fin produce una ilusión de comprensión; sin recuperación activa (active recall) y repaso espaciado, a la semana se ha olvidado la mayor parte.
3. **Los PDFs son hostiles al audio.** Un TTS ingenuo lee cabeceras, pies de página, citas `[12]`, URLs, tablas y ecuaciones tal cual — el resultado es inescuchable en documentos reales.
4. **No todo el PDF vale lo mismo.** El 20% del documento contiene el 80% del valor, pero un lector lineal (visual o de audio) no lo distingue: obliga a tragarse todo o a saltar a ciegas.
5. **Escuchar es unidireccional.** Con audio puro no puedes preguntar "¿qué significa esto?", "¿por qué?", "ponme un ejemplo" — que es exactamente lo que hace que una clase con un buen profesor supere a un audiolibro.

**Usuario objetivo inicial:** una persona que aprende de forma intensiva por su cuenta (papers, libros técnicos, temarios) y quiere convertir tiempo muerto en tiempo de aprendizaje real, no solo en "haber escuchado algo".

## 2. Estado del arte (agosto 2026)

| Producto | Qué hace bien | Qué le falta |
|---|---|---|
| **Speechify** (~50M usuarios) | TTS multiplataforma, 200+ voces, hasta 4.5x, mantiene layout del PDF | Lectura lineal pasiva. Cero comprensión del contenido, cero aprendizaje activo |
| **ElevenReader** (ElevenLabs) | Mejor calidad de voz del mercado, GenFM (podcast del doc) | Extracción de PDF floja en docs complejos (tablas, multicolumna, papers). Pasivo |
| **Listening.com** ($12.99/mes) | Especializado en papers: salta citas, pronuncia términos científicos (~95%), describe tablas/figuras, notas y bookmarks | Solo académico. No hay Q&A conversacional, ni quizzes, ni repaso espaciado |
| **NotebookLM (Audio Overviews)** | Podcast de 2 voces sobre tus fuentes, modo interactivo para "unirte" a la conversación, 80+ idiomas | Es un *resumen*, no el documento: formato fijo, inexactitudes, no sirve para cobertura completa ni estudio serio |
| **Recall / RemNote / Knowt / Studr** | Quizzes y flashcards desde PDF, repaso espaciado (active recall) | Sin audio o con audio de segunda. Son apps de estudio visual, no de escucha |
| **NaturalReader, IReadAll, etc.** | TTS gratuito decente, limpieza de orden de lectura | Mismo patrón: lectura pasiva lineal |

**El hueco:** el mercado está partido en dos mitades que no se hablan.
- Los **lectores de audio** (Speechify, ElevenReader, Listening) hacen *escuchar* pero no *aprender*: cero interacción, cero retención.
- Las **apps de estudio** (Recall, RemNote) hacen *retener* pero no *escuchar*: te devuelven a la silla y la pantalla.
- NotebookLM insinúa el puente (audio + interacción) pero renuncia a la fidelidad: genera un podcast-resumen, no te lleva por el documento.

Nadie ofrece hoy el ciclo completo **escuchar → preguntar → ser preguntado → repasar** sobre el documento real. Ese es el sitio de listenyourPDFs.

## 3. La solución

**listenyourPDFs = un tutor de audio para tus PDFs.** No un lector que habla, sino un profesor que te lleva por el documento por los oídos, al nivel de profundidad que elijas, y se asegura de que lo que oyes se te queda.

### Los tres pilares

1. **Audio inteligente del documento real** — ingesta que entiende la estructura (secciones, citas, tablas, ecuaciones, figuras) y produce una "pista de audio" limpia y fiel, con niveles de zoom: resumen (5 min) → recorrido guiado (20 min) → texto completo limpio.
2. **Interacción por voz** — en cualquier momento puedes interrumpir y preguntar ("explícame esto", "¿por qué?", "dame un ejemplo", "salta a la sección de resultados") y el tutor responde *anclado al documento* y retoma donde iba.
3. **Aprendizaje activo integrado** — el tutor te lanza preguntas al cerrar cada sección (active recall), y lo fallado/marcado entra en una cola de repaso espaciado que se sirve también en audio en sesiones posteriores.

El "10x" no viene de leer más rápido, sino de: tiempo muerto convertido en estudio (2-3x) × priorización del 20% que importa (2x) × retención real por recall+repaso (2x sobre lectura pasiva).

## 4. Requisitos funcionales

Prioridad MoSCoW: **M** (must, MVP) / **S** (should, v1) / **C** (could, después).

### RF-1. Ingesta y comprensión del documento
- **RF-1.1 (M)** Subir PDF (drag & drop / selector). Soportar PDFs nativos de texto.
- **RF-1.2 (M)** Extraer estructura: título, secciones, párrafos, orden de lectura correcto en multicolumna.
- **RF-1.3 (M)** Limpieza para audio: eliminar cabeceras/pies repetidos, números de página, citas inline (configurables), URLs; expandir abreviaturas y símbolos.
- **RF-1.4 (S)** Tablas y figuras: generar descripción hablada breve ("La tabla 2 compara X e Y; lo relevante es…").
- **RF-1.5 (S)** Ecuaciones: leerlas en lenguaje natural o saltarlas con resumen, según preferencia.
- **RF-1.6 (C)** OCR para PDFs escaneados.
- **RF-1.7 (C)** Otras fuentes: EPUB, URL de artículo, arXiv ID.

### RF-2. Niveles de escucha (zoom)
- **RF-2.1 (M)** Nivel *Completo*: el documento entero, limpio, en audio.
- **RF-2.2 (M)** Nivel *Resumen*: síntesis fiel de ~5 min con las ideas clave y su estructura.
- **RF-2.3 (S)** Nivel *Recorrido guiado*: versión intermedia generada por sección (idea principal + detalle importante), estilo "profesor explicando el paper".
- **RF-2.4 (S)** Cambiar de nivel en caliente sin perder la posición ("amplíame esta sección" / "resume el resto").

### RF-3. Reproducción
- **RF-3.1 (M)** Play/pausa, velocidad 0.75x–3x, saltar ±15s, saltar por sección.
- **RF-3.2 (M)** TTS de calidad natural, español e inglés como mínimo.
- **RF-3.3 (M)** La posición se sincroniza con el texto: al escuchar se resalta el párrafo actual (modo pantalla) y al abrir el PDF ves por dónde vas.
- **RF-3.4 (S)** Escucha en background y con pantalla bloqueada (controles del sistema / lock screen).
- **RF-3.5 (C)** Descarga offline del audio generado.

### RF-4. Interacción con el tutor
- **RF-4.1 (M)** Preguntar por texto en cualquier momento; respuesta anclada al documento (con referencia a la sección) y opción "no está en el documento" explícita — nunca inventar.
- **RF-4.2 (S)** Preguntar por voz (push-to-talk o palabra de activación) y respuesta por voz; al terminar, la reproducción retoma donde estaba.
- **RF-4.3 (S)** Comandos de navegación por voz: "salta a resultados", "repite eso", "más despacio", "resume este capítulo".
- **RF-4.4 (C)** Modo debate/socrático: el tutor defiende una postura del documento y tú la atacas.

### RF-5. Aprendizaje activo y retención
- **RF-5.1 (M)** Al cerrar cada sección (o cada N minutos), el tutor hace 1-3 preguntas de recuperación sobre lo escuchado; el usuario responde (voz o texto) y recibe corrección breve.
- **RF-5.2 (M)** Marcar momentos ("esto es oro" / "no lo entiendo") con un tap o comando de voz; queda guardado con timestamp + párrafo.
- **RF-5.3 (S)** Cola de repaso espaciado (FSRS): lo fallado y lo marcado se reprograma; cada sesión empieza con 2-5 min de repaso en audio de documentos anteriores.
- **RF-5.4 (S)** Notas automáticas: al terminar un documento, generar una ficha (resumen + tus marcas + preguntas y tu rendimiento) exportable en Markdown.
- **RF-5.5 (C)** Export a Obsidian/Anki.

### RF-6. Biblioteca y progreso
- **RF-6.1 (M)** Biblioteca de documentos con estado (sin empezar / en curso con % / terminado) y posición guardada.
- **RF-6.2 (S)** Estadísticas: tiempo escuchado, % de acierto en preguntas, elementos en cola de repaso.
- **RF-6.3 (C)** Colecciones/carpetas y búsqueda semántica en toda la biblioteca ("¿en qué paper hablaban de X?").

### RF-7. Plataforma y self-hosting
- **RF-7.1 (M)** Web app responsive usable desde el móvil (PWA-friendly): el caso de uso principal es móvil + auriculares.
- **RF-7.2 (M)** BYOK: las API keys (LLM y TTS) se configuran por variables de entorno del que lo despliega; nunca se suben al repo.
- **RF-7.3 (M)** Despliegue en un comando (Docker Compose o similar) con documentación de self-hosting en el README.
- **RF-7.4 (S)** Proveedores de LLM/TTS intercambiables tras una interfaz común (que cada uno use el que quiera/pueda pagar).
- **RF-7.5 (C)** Multiusuario con autenticación, para quien despliegue una instancia compartida.
- **RF-7.6 (C)** Apps nativas iOS/Android si la PWA se queda corta (audio en background es el riesgo a validar).

## 5. Requisitos no funcionales (mínimos)

- **RNF-1** Latencia: de subir un PDF de ~20 páginas a poder darle play, < 60s (el resto del audio se genera en streaming/por delante de la posición de escucha).
- **RNF-2** Coste por documento controlado: cachear audio generado; no regenerar lo ya sintetizado.
- **RNF-3** Privacidad: los PDFs del usuario no se usan para entrenar nada; borrado real al eliminar.
- **RNF-4** Fidelidad: en niveles Resumen/Recorrido, todo lo afirmado debe ser trazable al documento (anti-alucinación); las respuestas del tutor citan sección.

## 6. Alcance del MVP (propuesta)

Todo lo marcado **M**: subir PDF nativo → extracción + limpieza → audio Completo y Resumen con TTS natural (ES/EN) → reproductor con sync de texto → Q&A por texto anclado al doc → preguntas de recall por sección → marcas → biblioteca con progreso → BYOK + despliegue en un comando.

Fuera del MVP: voz bidireccional, repaso espaciado, OCR, tablas/ecuaciones habladas, multiusuario, apps nativas.

**Criterio de éxito del MVP:** el autor termina un paper de 15 páginas íntegramente andando, responde bien >70% de las preguntas de recall al día siguiente, y lo prefiere a Speechify/Listening.com. Segundo criterio (OSS): otra persona consigue desplegarlo con sus keys siguiendo solo el README.

## 7. Decisiones tomadas

- **Open source (MIT), personal-first.** No hay objetivo de monetización; el valor es la herramienta en sí, el aprendizaje y el portfolio. (2026-08-04)
- **Mono-usuario en el MVP.** Sin auth ni pagos; multiusuario queda como C para instancias compartidas. (2026-08-04)

## 8. Preguntas abiertas

1. ¿Voz bidireccional en v1 o validar antes con Q&A por texto? (La voz es el "wow" pero dispara coste y complejidad.)
2. ¿PWA vs nativo? El audio en background con pantalla bloqueada en iOS-PWA es limitado — riesgo técnico nº 1 a validar la primera semana.
3. Motor TTS por defecto: calidad (ElevenLabs) vs coste (OpenAI TTS / Google / TTS local tipo Kokoro para self-hosting 100% gratis) — decidir con una prueba ciega sobre un paper real en español.
4. Stack: definir en `docs/02-arquitectura.md` (siguiente paso).
