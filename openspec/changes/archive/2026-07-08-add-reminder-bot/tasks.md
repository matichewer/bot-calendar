## 1. Fundaciones del proyecto

- [x] 1.1 Crear estructura del proyecto Python (paquete `bot/`, `pyproject.toml` o `requirements.txt` con python-telegram-bot v21+, APScheduler, python-dateutil, groq)
- [x] 1.2 Módulo de configuración: cargar y validar `.env` (`TELEGRAM_TOKEN`, `GROQ_API_KEY`, `ALLOWED_CHAT_ID`, `TZ`); fallar al arrancar si falta algo obligatorio
- [x] 1.3 Capa de persistencia SQLite: creación del esquema `reminders` (D4) al arrancar, funciones CRUD (crear, listar activos, actualizar próxima ejecución/estado, cancelar)
- [x] 1.4 Esqueleto del bot con long polling, comando `/start` con mensaje de bienvenida en español, y filtro global de whitelist por `ALLOWED_CHAT_ID` que ignora en silencio a cualquier otro chat

## 2. Fase 1 — Texto, confirmación y scheduler

- [x] 2.1 Cliente Groq de parseo NL: prompt con fecha/hora actual + zona horaria, salida JSON `{mensaje, fecha_hora_iso, recurrencia_rrule|null, aclaracion|null}`; manejo de errores/rate limit con mensaje de reintento al usuario
- [x] 2.2 Handler de mensajes de texto: interpretar el pedido; si hay `aclaracion`, preguntarla; si el mensaje no es un pedido de recordatorio, explicar qué sabe hacer el bot
- [x] 2.3 Tarjeta de confirmación con botones inline ✅/❌ mostrando texto, fecha/hora formateada en español y recurrencia si hay; pendiente en `context.user_data`, un nuevo pedido descarta al anterior
- [x] 2.4 Callback de confirmación: al confirmar, persistir en SQLite y programar en APScheduler; al cancelar, descartar y avisar
- [x] 2.5 Scheduler: disparo del recordatorio por Telegram; únicos → `completado`; recurrentes → calcular próxima ocurrencia con `dateutil.rrule` y reprogramar
- [x] 2.6 Recuperación al arranque: recargar activos desde SQLite, enviar vencidos como "atrasados" (recurrentes: un solo aviso y reprogramar a la próxima ocurrencia futura)
- [x] 2.7 Comando `/lista`: mostrar activos con próxima ejecución y recurrencia, con botones para cancelar (desprogramar + estado `cancelado`)
- [x] 2.8 Probar fase 1 de punta a punta: pedido único, recurrente, ambiguo, cancelación desde lista, y reinicio del proceso con un recordatorio vencido

## 3. Fase 2 — Notas de voz

- [x] 3.1 Handler de notas de voz: descargar el `.ogg` de Telegram y transcribirlo con Groq `whisper-large-v3-turbo` (español)
- [x] 3.2 Encaminar la transcripción por el mismo flujo de interpretación/confirmación que el texto; ante transcripción fallida o vacía, pedir reintento sin crear nada
- [x] 3.3 Probar fase 2: nota de voz válida produce la misma tarjeta que el texto equivalente

## 4. Fase 3 — Espejo en Google Calendar

- [x] 4.1 Script único de autorización (`scripts/google_auth.py`) para correr en la PC: flujo OAuth de escritorio que genera `token.json`; documentar en README el paso a paso de Google Cloud (app "En producción" para refresh token permanente)
- [x] 4.2 Cliente de Calendar: crear evento (con RRULE si aplica) al confirmar, guardar `gcal_event_id`; borrar evento al cancelar el recordatorio
- [x] 4.3 Desacople total: sin `token.json` la feature queda apagada sin errores; falla de API → el recordatorio sigue y se avisa breve; refresh token revocado → desactivar espejo y avisar una sola vez
- [x] 4.4 Probar fase 3: espejo de único y recurrente visibles en Calendar, cancelación borra el evento, y el bot completo funciona sin token

## 5. Despliegue en la Raspberry

- [x] 5.1 `Dockerfile` (python slim, compatible arm64) y `docker-compose.yml` con `restart: unless-stopped`, `.env`, `TZ` y volumen `./data` (SQLite + tokens)
- [x] 5.2 `README.md`: setup completo (BotFather, API key de Groq, obtener chat ID, OAuth de Google, despliegue con `docker compose up -d --build`)
- [x] 5.3 Desplegar en la Pi 4B y verificar en real: recordatorio por texto y por audio, uno recurrente, y supervivencia a un reinicio de la Pi
