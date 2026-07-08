# bot-calendar 🤖🔔

Bot personal de Telegram para crear recordatorios en lenguaje natural (texto o
nota de voz), con recurrencia y espejo opcional en Google Calendar. Corre en una
Raspberry Pi con docker compose. Costo: **$0/mes**.

> «recordame sacar la basura todos los lunes a las 8» → tarjeta de confirmación
> → 🔔 mensaje por Telegram cada lunes a las 8.

## Cómo funciona

- **Groq** (free tier) interpreta el pedido (Llama 3.3 70B) y transcribe los audios (Whisper).
- Todo pedido se **confirma con botones** antes de guardarse.
- Los recordatorios viven en **SQLite** (`data/reminders.db`) y los dispara
  **APScheduler**; si la Pi se reinicia, al arrancar se reprograma todo y lo
  vencido se envía marcado como atrasado.
- Si configurás Google Calendar, cada recordatorio se **espeja como evento**;
  si Calendar falla, el recordatorio funciona igual.
- El bot atiende **solo a tu chat** (`ALLOWED_CHAT_ID`); ignora a cualquier otro.

## Setup

### 1. Crear el bot en Telegram

1. Hablale a [@BotFather](https://t.me/BotFather) → `/newbot` → elegí nombre y usuario.
2. Guardá el **token** que te da.
3. Para conocer tu **chat ID**: mandale `/start` a [@userinfobot](https://t.me/userinfobot).

### 2. API key de Groq (gratis)

1. Entrá a [console.groq.com/keys](https://console.groq.com/keys) (login con Google/GitHub, sin tarjeta).
2. Creá una API key y guardala.

### 3. Configurar

```bash
cp .env.example .env
nano .env   # completá TELEGRAM_TOKEN, GROQ_API_KEY, ALLOWED_CHAT_ID, TZ
```

### 4. Levantar en la Raspberry

```bash
docker compose up -d --build
docker compose logs -f   # para ver que arrancó bien
```

Mandale `/start` al bot y probá: *«recordame regar las plantas mañana a las 19»*.

## Google Calendar (opcional)

Se hace **una sola vez desde tu PC** (no en la Pi):

1. **Proyecto**: [console.cloud.google.com](https://console.cloud.google.com) → Nuevo proyecto (ej. `bot-calendar`).
2. **API**: APIs y servicios → Biblioteca → **Google Calendar API** → Habilitar.
3. **Pantalla de consentimiento**: tipo **Externo**, completá solo nombre y tu email.
4. **⚠️ Importante**: dejá el estado de publicación **"En producción"** (no
   "Prueba"). En modo Prueba, Google vence el refresh token **cada 7 días**.
   En producción sin verificar solo verás una pantalla de "app no verificada"
   una única vez durante el login (→ "Continuar de todos modos").
5. **Credenciales**: Credenciales → Crear credenciales → **ID de cliente de OAuth**
   → tipo **Aplicación de escritorio** → descargá el `credentials.json`.
6. **Login** (en tu PC):
   ```bash
   pip install google-auth-oauthlib
   python scripts/google_auth.py ruta/al/credentials.json
   ```
   Se abre el navegador, autorizás, y se genera `token.json`.
7. **Copiar a la Pi**: poné `credentials.json` y `token.json` en `data/` del
   proyecto y reiniciá el bot (`docker compose restart`).

Sin `token.json`, el bot funciona completo — simplemente no espeja al calendario.
Si algún día el token se revoca, el bot te avisa una vez y seguís sin espejo
hasta repetir los pasos 6–7.

## Uso

| Acción | Cómo |
|---|---|
| Crear recordatorio | Escribí o mandá audio: «recordame X mañana a las 10» |
| Recurrente | «...todos los lunes a las 8», «...cada 15 días» |
| Ver activos | `/lista` |
| Cancelar uno | `/lista` → botón 🗑 |

## Estructura

```
bot/
├── main.py        # arranque, handlers, polling
├── config.py      # .env y validación
├── db.py          # SQLite (fuente de verdad)
├── nlp.py         # Groq: parseo NL y transcripción
├── scheduler.py   # APScheduler: disparo, recurrencia, recuperación
├── handlers.py    # flujo de Telegram (confirmación, /lista, voz)
├── gcal.py        # espejo en Google Calendar (opcional)
└── formatting.py  # fechas y recurrencias en español
```
