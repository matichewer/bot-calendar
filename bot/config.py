"""Carga y validación de la configuración desde variables de entorno / .env."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

OBLIGATORIAS = ("TELEGRAM_TOKEN", "GROQ_API_KEY", "ALLOWED_CHAT_ID", "TZ")


@dataclass(frozen=True)
class Config:
    telegram_token: str
    groq_api_key: str
    allowed_chat_id: int
    tz: ZoneInfo
    tz_name: str
    db_path: Path
    groq_model: str
    groq_whisper_model: str
    google_token_path: Path
    google_credentials_path: Path
    gcal_calendar_id: str


def cargar_config() -> Config:
    """Lee el entorno (y un .env si existe). Sale con error claro si falta algo."""
    load_dotenv()

    faltantes = [var for var in OBLIGATORIAS if not os.environ.get(var)]
    if faltantes:
        print(
            "ERROR: faltan variables de entorno obligatorias: "
            + ", ".join(faltantes)
            + "\nCompletá el archivo .env (ver .env.example).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    chat_id_raw = os.environ["ALLOWED_CHAT_ID"]
    try:
        allowed_chat_id = int(chat_id_raw)
    except ValueError:
        print(
            f"ERROR: ALLOWED_CHAT_ID debe ser un número entero, no {chat_id_raw!r}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    tz_name = os.environ["TZ"]
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        print(
            f"ERROR: TZ={tz_name!r} no es una zona horaria válida "
            "(ejemplo: America/Argentina/Buenos_Aires).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        telegram_token=os.environ["TELEGRAM_TOKEN"],
        groq_api_key=os.environ["GROQ_API_KEY"],
        allowed_chat_id=allowed_chat_id,
        tz=tz,
        tz_name=tz_name,
        db_path=Path(os.environ.get("DB_PATH", data_dir / "reminders.db")),
        groq_model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_whisper_model=os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
        google_token_path=Path(os.environ.get("GOOGLE_TOKEN_PATH", data_dir / "token.json")),
        google_credentials_path=Path(
            os.environ.get("GOOGLE_CREDENTIALS_PATH", data_dir / "credentials.json")
        ),
        gcal_calendar_id=os.environ.get("GCAL_CALENDAR_ID", "primary"),
    )
