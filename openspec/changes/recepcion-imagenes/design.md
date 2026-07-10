# Diseño: recepción de imágenes con detección de eventos

## Context

El bot corre en una Pi 4B, usa Groq (`llama-3.3-70b-versatile`) vía `AsyncGroq` para interpretar texto y Whisper para voz. El flujo actual: `_procesar_pedido` → `Interpretacion` (un solo recordatorio, o una aclaración) → `_mostrar_confirmacion` guarda **una única** propuesta en `context.user_data["pendiente"]` (token, msg_id, datos) → `callback_confirmacion` la valida por token y persiste vía `db` + `scheduler` + `gcal`.

Restricciones:
- `llama-3.3-70b-versatile` no acepta imágenes; hace falta un modelo multimodal para las fotos.
- El estado pendiente es de una sola propuesta; una imagen puede producir N eventos.
- La propuesta de texto participa de un flujo de corrección conversacional (`_contexto_pendiente`); replicar eso para N tarjetas de imagen es complejidad desproporcionada para un bot personal.

## Goals / Non-Goals

**Goals:**
- Aceptar fotos (invitaciones, cronogramas) y extraer todos los eventos presentes.
- Confirmación individual por evento, coexistiendo con el flujo de texto sin romperlo.
- Reusar sin cambios DB, scheduler y espejo de Google Calendar.

**Non-Goals:**
- Corrección conversacional de tarjetas de imagen («que el segundo sea a las 10»): las tarjetas de imagen son confirmar/cancelar solamente. Si algo salió mal, el usuario cancela esa tarjeta y pide el recordatorio por texto.
- OCR local (Tesseract): descartado — peor calidad en tipografías decorativas/tablas y de todas formas requeriría el LLM después.
- Documentos adjuntos (`filters.Document.IMAGE`), PDFs, álbumes (media groups): fuera de alcance; solo fotos comprimidas de Telegram (`filters.PHOTO`).
- Persistencia de pendientes entre reinicios (el estado ya es en memoria hoy; no cambia).

## Decisions

### D1 — Modelo de visión de Groq, configurable
Nueva variable `GROQ_VISION_MODEL` (default `meta-llama/llama-4-scout-17b-16e-instruct`). Se reusa el cliente `AsyncGroq` existente; la imagen viaja como data URL base64 en un mensaje `user` multimodal. Alternativas: Maverick (más capaz, ~2× precio) queda disponible cambiando la variable; OCR local descartado (ver Non-Goals).

**Nota de implementación**: los modelos de visión de Groq no soportan `response_format json_object` junto con imágenes en todos los casos y son menos confiables con mensajes `system`; el prompt de visión va como texto en el mismo turno `user` que la imagen, pidiendo JSON, y el parseo tolera texto alrededor del JSON (extraer el primer bloque `{...}`/`[...]`).

### D2 — Nuevo método `NLP.interpretar_imagen()` con prompt propio
Devuelve `list[Interpretacion]` (reusa el dataclass existente; `aclaracion` no se usa en este flujo). Prompt específico de visión con las mismas convenciones que el de texto (zona horaria, contexto de fecha actual con días de semana explícitos, no inventar datos) más reglas propias:
- Devolver un array JSON de eventos: `[{"mensaje", "fecha_hora_iso", "recurrencia_rrule"}]`.
- Evento **sin fecha deducible** → se omite del array y se lista en una clave aparte `"omitidos": ["..."]` para informarlo al usuario. No hay hilo de aclaración por evento.
- Evento **sin hora** → 09:00 por defecto (la tarjeta lo muestra, el usuario puede cancelarla).
- Año ausente → la próxima ocurrencia futura.
- El caption de la foto, si existe, se agrega como contexto del usuario.
- Cap de 10 eventos por imagen (defensa contra salidas degeneradas del modelo).

La validación por evento reusa `_validar` (fecha parseable, futura, rrule válida); un evento que no valida se descarta y se cuenta entre los omitidos, sin abortar el resto.

### D3 — Estado pendiente: dict separado para tarjetas de imagen
`context.user_data["pendientes_imagen"]: dict[token, propuesta]` conviviendo con el `"pendiente"` actual (que no cambia). Razón: la propuesta de texto arrastra semántica extra (reemplazo por pedido nuevo, contexto de corrección); mezclarlas en una sola estructura obligaría a casos especiales por todos lados. Costo aceptado: dos estructuras de estado pendiente.

- Un pedido de texto nuevo reemplaza solo `"pendiente"`; las tarjetas de imagen quedan vigentes.
- Una **foto nueva** reemplaza las tarjetas de imagen anteriores no respondidas (mismo criterio de «lo más nuevo manda» que el flujo de texto): se editan sus mensajes a «↩️ Reemplazado…» y se limpia el dict.
- Cap del dict: al insertar, si hay tarjetas viejas de una foto anterior no puede pasar (se limpian antes); dentro de una misma foto el cap de 10 de D2 acota el tamaño.

### D4 — Callback de confirmación unificado
Se mantiene el patrón `conf:si|no:<token>` y el handler existente. Orden de resolución en `callback_confirmacion`: primero `"pendiente"` (comportamiento actual intacto), después `pendientes_imagen[token]`. Confirmar una tarjeta de imagen ejecuta el mismo camino de persistencia (extraído a un helper `_confirmar_propuesta` para no duplicar: `db.crear` + `scheduler.programar` + `gcal.crear_evento` + edición del mensaje). Cancelar elimina solo esa entrada del dict. Token desconocido → mensaje «ya no está vigente» actual.

### D5 — Handler de fotos
`MessageHandler(filters.PHOTO, handlers.foto)` registrado en `main.py` (la whitelist en group -1 ya lo cubre). Toma `update.message.photo[-1]` (mayor resolución, que Telegram ya comprime a ≤~1280px — dentro de los límites de Groq), descarga bytes, llama a `interpretar_imagen(bytes, caption)`. Respuestas:
- 0 eventos y sin omitidos → «No encontré fechas en la imagen…».
- N eventos → mensaje introductorio («📸 Encontré N eventos») + una tarjeta por evento.
- Omitidos → línea informativa al final («⚠️ No pude ubicar fecha para: …»).
- `NLPError` → mismo mensaje de degradación que texto (`MENSAJE_SIN_SERVICIO`).

## Risks / Trade-offs

- [El modelo de visión alucina fechas u eventos inexistentes] → La confirmación explícita por tarjeta es la barrera: nada se guarda sin ✅. Prompt insiste en no inventar; validación descarta fechas pasadas/incoherentes.
- [Salida del modelo no es JSON limpio] → Parseo tolerante (extraer primer bloque JSON) + descarte por evento en `_validar`; si nada parsea, se trata como 0 eventos con aviso.
- [Cronogramas grandes producen spam de tarjetas] → Cap de 10 eventos por imagen; el mensaje introductorio anuncia cuántas tarjetas siguen.
- [Dos estructuras de estado pendiente divergen con el tiempo] → Helper de persistencia compartido (`_confirmar_propuesta`) concentra el camino común; las estructuras solo difieren en ciclo de vida.
- [Llama 4 Scout interpreta peor el español de imágenes que el flujo de texto] → Variable de entorno permite subir a Maverick sin tocar código.

## Migration Plan

Sin migraciones de datos. Deploy: `git pull` + rebuild del contenedor en la Pi con la nueva variable en `.env` (tiene default, no es obligatoria). Rollback: volver al commit anterior; el estado nuevo vive solo en memoria.

## Open Questions

- Ninguna bloqueante. Si en el uso real los defaults (09:00 para eventos sin hora, cap de 10) resultan incómodos, se ajustan como constantes.
