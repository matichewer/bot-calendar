## Why

Necesito una forma sin fricción de crear recordatorios: decirle a un bot de Telegram, por texto o audio y en español natural, qué debe recordarme y cuándo, y recibir el aviso por Telegram en ese momento. Las apps de recordatorios existentes exigen formularios o sintaxis rígida; un bot con LLM entiende "recordame llamar al médico mañana a las 10" directamente. Debe correr en mi Raspberry Pi 4B con docker compose y costar $0/mes.

## What Changes

- Nuevo bot de Telegram (proyecto greenfield, no hay código previo) que:
  - Recibe pedidos de recordatorio en lenguaje natural, por **texto** y por **nota de voz** (transcripción vía Groq Whisper).
  - Interpreta el pedido con un LLM (Groq, Llama 3.3 70B) extrayendo mensaje, fecha/hora y recurrencia opcional.
  - Pide **confirmación con botones inline** (confirmar / cancelar) antes de guardar, mostrando lo interpretado.
  - Persiste los recordatorios en SQLite y los dispara con un scheduler que **sobrevive reinicios** de la Raspberry.
  - Envía el mensaje recordatorio por Telegram en la fecha/hora pactada; los recurrentes se reprograman solos.
  - Soporta recordatorios **únicos y recurrentes** ("todos los lunes a las 8") desde la v1.
  - **Espeja** cada recordatorio confirmado como evento en Google Calendar (opcional, fase 3; el bot sigue siendo la fuente de verdad).
  - Atiende a un **único usuario** (whitelist por chat ID); ignora a cualquier otro.
  - Opera íntegramente en español.
- Despliegue con docker compose en Raspberry Pi 4B (arm64), long polling (sin puertos abiertos), secretos por `.env`, datos en volumen persistente.

Entrega en fases: **F1** texto + únicos y recurrentes + confirmación + scheduler; **F2** audio; **F3** espejo Google Calendar.

## Capabilities

### New Capabilities
- `reminder-capture`: entender pedidos en lenguaje natural (texto y audio) vía LLM y flujo de confirmación con botones antes de guardar.
- `reminder-scheduling`: persistencia en SQLite, disparo puntual de recordatorios por Telegram, recurrencia y recuperación tras reinicios.
- `calendar-mirror`: creación espejo de eventos en Google Calendar vía OAuth (desktop app, refresh token permanente); fallos del espejo no afectan al recordatorio.
- `bot-access-control`: restricción del bot a un único chat ID autorizado.

### Modified Capabilities

(ninguna — proyecto nuevo, no existen specs previas)

## Impact

- Código: proyecto nuevo completo (Python, python-telegram-bot, APScheduler, SQLite, clientes Groq y Google Calendar).
- Dependencias externas: Telegram Bot API, Groq API (free tier: Whisper + Llama), Google Calendar API (fase 3).
- Infraestructura: docker compose en Raspberry Pi 4B; volumen para SQLite y token de Google; `.env` con `TELEGRAM_TOKEN` y `GROQ_API_KEY`.
- Setup manual único: crear bot con BotFather, obtener API key de Groq, y (fase 3) flujo OAuth de Google desde una PC con la app publicada "En producción" para que el refresh token no venza.
