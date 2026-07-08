## Context

Proyecto greenfield: no existe código. El sistema es un bot de Telegram de recordatorios en español, para un único usuario, corriendo 24/7 en una Raspberry Pi 4B (8 GB, arm64) con docker compose, con costo operativo $0/mes. Decisiones de producto ya tomadas en exploración: el bot es la fuente de verdad de los recordatorios (Google Calendar es solo espejo), la entrada es lenguaje natural por texto o nota de voz, y toda interpretación pasa por una confirmación explícita antes de guardarse.

Restricciones:
- La Pi está detrás de un router hogareño sin puertos abiertos ni dominio → no hay webhooks entrantes.
- Free tiers: Groq (Whisper + Llama) con límites de rate generosos para uso personal; Telegram Bot API gratis; Google Calendar API con cuota sobrada.
- La Pi puede reiniciarse (cortes de luz, updates): ningún recordatorio puede perderse por eso.

## Goals / Non-Goals

**Goals:**
- Crear recordatorios diciéndolo en español natural (texto o audio) y recibir el aviso por Telegram en el momento exacto.
- Recordatorios únicos y recurrentes desde la v1.
- Confirmación con botones inline antes de persistir (el LLM puede interpretar mal).
- Supervivencia a reinicios: al arrancar, el bot recompone su agenda desde SQLite y dispara lo vencido.
- Espejo opcional en Google Calendar (fase 3) sin acoplar la funcionalidad principal a él.
- Despliegue reproducible con `docker compose up -d` en arm64.

**Non-Goals:**
- Multiusuario, grupos, o compartir recordatorios.
- Sincronización bidireccional con Google Calendar (leer/editar eventos creados fuera del bot).
- Snooze, listas de tareas, prioridades u otras features de app de productividad (pueden venir después; el modelo de datos no debe impedirlas).
- Webhooks de Telegram, HTTPS, dominios.
- Transcripción local en la Pi (whisper.cpp): descartada a favor de API.

## Decisions

### D1. Stack: Python + python-telegram-bot + APScheduler + SQLite
Un solo proceso, un solo contenedor. `python-telegram-bot` (v21+, asyncio) es la librería más madura y documentada para bots; APScheduler comparte el event loop y evita un servicio de colas aparte; SQLite evita un contenedor de base de datos. Alternativas consideradas: aiogram (equivalente, menos documentación en español), Celery/Redis (sobredimensionado para un usuario), Node.js (sin ventaja y el ecosistema de scheduling es más débil).

### D2. Long polling, no webhooks
`run_polling()` mantiene una conexión saliente hacia Telegram. Cero configuración de red en la Pi. El costo (latencia de ~1 s) es irrelevante para este caso.

### D3. Groq como único proveedor de IA
Una sola API key cubre transcripción (`whisper-large-v3-turbo`) y parseo NL (`llama-3.3-70b-versatile`), ambas en free tier. El parseo usa **salida JSON estructurada**: se le pasa al LLM el mensaje del usuario + fecha/hora actual + zona horaria, y debe devolver `{mensaje, fecha_hora_iso, recurrencia|null, aclaracion|null}`. Si el LLM no puede resolver el pedido (falta la hora, fecha ambigua), devuelve `aclaracion` con la pregunta a hacerle al usuario en vez de inventar. Alternativa considerada: Gemini Flash (audio nativo, un solo call); queda como plan B documentado si el free tier de Groq cambia.

### D4. Modelo de datos: `proxima_ejecucion` + regla de recurrencia opcional
Tabla `reminders`:

```
id INTEGER PK
chat_id INTEGER          -- redundante hoy (un usuario), a prueba de futuro
texto TEXT               -- qué recordar
proxima_ejecucion TEXT   -- ISO 8601 con zona horaria; lo ÚNICO que mira el scheduler
recurrencia TEXT NULL    -- regla RRULE (RFC 5545) o NULL si es único
estado TEXT              -- 'activo' | 'completado' | 'cancelado'
gcal_event_id TEXT NULL  -- id del evento espejo en Google Calendar (fase 3)
creado_en TEXT
```

El scheduler solo conoce `proxima_ejecucion`. Al dispararse un recordatorio: si `recurrencia` es NULL → estado `completado`; si no → se calcula la próxima ocurrencia con `dateutil.rrule` y se actualiza `proxima_ejecucion`. RRULE en vez de un formato propio porque `python-dateutil` lo parsea nativo y es el mismo formato que usa Google Calendar (el espejo de recurrentes sale gratis).

### D5. Recuperación tras reinicio
Al arrancar, el bot lee todos los recordatorios `activo` de SQLite y los registra en APScheduler (jobs en memoria; SQLite es la única persistencia — un solo dueño del estado). Los que quedaron vencidos durante el apagón se envían inmediatamente con una marca de "atrasado", y los recurrentes se reprograman a su próxima ocurrencia futura. Alternativa considerada: jobstore persistente de APScheduler; descartado por duplicar la fuente de verdad.

### D6. Flujo de confirmación con estado pendiente en memoria
Interpretación → tarjeta de confirmación (texto interpretado + fecha/hora formateada + recurrencia si hay) con botones ✅ Confirmar / ❌ Cancelar. El recordatorio pendiente vive en memoria (`context.user_data`) hasta el tap; solo al confirmar se escribe en SQLite y se programa. Si el usuario manda otro pedido con una confirmación pendiente, la pendiente se descarta (la más reciente gana). No hay botón "editar": corregir es cancelar y repetir el pedido, que en lenguaje natural cuesta lo mismo.

### D7. Espejo en Google Calendar desacoplado (fase 3)
Tras confirmar, se intenta crear el evento en Calendar (con RRULE si es recurrente) y se guarda `gcal_event_id`. Si Calendar falla (sin red, token inválido, feature no configurada), el recordatorio funciona igual y se avisa discretamente. OAuth de app de escritorio con la app publicada "En producción" (evita el vencimiento semanal del refresh token en modo Testing); `credentials.json` + `token.json` en el volumen. Si no hay token, la feature queda apagada sin error.

### D8. Control de acceso por whitelist
`ALLOWED_CHAT_ID` en `.env`. Todo update cuyo chat no coincida se ignora en silencio (sin responder, para no confirmar la existencia del bot). Implementado como filtro global antes de cualquier handler.

### D9. Zona horaria explícita
`TZ` en `.env` (ej. `America/Argentina/Buenos_Aires`). Todas las fechas se almacenan en ISO 8601 con offset; el LLM recibe la hora local actual y la zona en el prompt. Sin esto, "mañana a las 10" es indefinido.

### D10. Docker: imagen única arm64, volumen para datos
Un `Dockerfile` (python slim, multiarch) y `docker-compose.yml` con `restart: unless-stopped`, `.env` para secretos y un volumen `./data` para SQLite + tokens de Google. `TZ` pasada al contenedor.

## Risks / Trade-offs

- [El LLM interpreta mal fecha/hora] → La confirmación obligatoria hace que el error cueste un tap; el prompt exige `aclaracion` ante ambigüedad en vez de adivinar.
- [Groq free tier caído o rate-limited] → El bot responde "no pude interpretar ahora, probá de nuevo"; los recordatorios ya guardados disparan igual (el scheduler no depende de Groq). Plan B documentado: Gemini Flash.
- [La Pi apagada a la hora de un recordatorio] → Al arrancar se envían los vencidos marcados como atrasados. Trade-off aceptado: si la Pi está muerta, no hay aviso — es la consecuencia de la opción A (bot fuente de verdad) que el usuario eligió a sabiendas.
- [Refresh token de Google revocado/vencido] → El espejo falla sin romper nada y el bot avisa una vez; re-ejecutar el flujo OAuth desde la PC lo repara.
- [Reloj de la Pi desfasado tras cortes largos (sin RTC)] → systemd-timesyncd corrige al recuperar red; los jobs son por fecha absoluta, no por delta.
- [Confirmaciones pendientes se pierden si el bot se reinicia] → Aceptado: es estado efímero de conversación; el usuario simplemente repite el pedido.

## Migration Plan

No hay migración (greenfield). Despliegue: `docker compose up -d --build` en la Pi. Rollback: `docker compose down` y volver a la imagen anterior; los datos en `./data` no se tocan. Setup manual único documentado en README: BotFather → token, console.groq.com → API key, y en fase 3 el flujo OAuth de Google desde una PC.

## Open Questions

- ¿Comandos de gestión (`/lista`, cancelar un recordatorio existente) en v1 o después? Se asume v1 mínimo: `/lista` y cancelación desde la lista con botones, porque sin eso los recurrentes son imborrables.
- Nombre del calendario destino del espejo: ¿el principal o uno dedicado "Bot"? Se asume el principal salvo que el usuario diga otra cosa.
