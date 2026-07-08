"""Espejo opcional de recordatorios en Google Calendar.

Nunca bloquea al bot: sin token la feature queda apagada; cualquier falla de la API
se degrada a un aviso. Si el refresh token muere, se desactiva hasta rehacer el login.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .config import Config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DURACION_EVENTO = timedelta(minutes=30)


class ResultadoEspejo:
    OK = "ok"
    FALLO = "fallo"          # falla transitoria: avisar breve
    DESACTIVADO = "desactivado"  # sin token o token muerto: no molestar (salvo 1ª vez)


class CalendarMirror:
    def __init__(self, config: Config):
        self._config = config
        self._service = None
        self._token_invalido = False
        self.aviso_token_pendiente = False  # True una sola vez cuando muere el token

    @property
    def habilitado(self) -> bool:
        return self._config.google_token_path.exists() and not self._token_invalido

    def _get_service(self):
        if self._service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_file(
                str(self._config.google_token_path), SCOPES
            )
            self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _marcar_token_muerto(self) -> None:
        self._token_invalido = True
        self._service = None
        self.aviso_token_pendiente = True
        logger.error("Token de Google inválido/revocado: espejo desactivado")

    def _es_error_de_token(self, exc: Exception) -> bool:
        try:
            from google.auth.exceptions import RefreshError
        except ImportError:
            return False
        return isinstance(exc, RefreshError)

    async def crear_evento(
        self, texto: str, inicio: datetime, rrule: Optional[str]
    ) -> tuple[str, Optional[str]]:
        """Devuelve (resultado, event_id)."""
        if not self.habilitado:
            return ResultadoEspejo.DESACTIVADO, None

        cuerpo = {
            "summary": texto,
            "start": {
                "dateTime": inicio.isoformat(),
                "timeZone": self._config.tz_name,
            },
            "end": {
                "dateTime": (inicio + DURACION_EVENTO).isoformat(),
                "timeZone": self._config.tz_name,
            },
        }
        if rrule:
            cuerpo["recurrence"] = [f"RRULE:{rrule}"]

        def _insertar():
            return (
                self._get_service()
                .events()
                .insert(calendarId=self._config.gcal_calendar_id, body=cuerpo)
                .execute()
            )

        try:
            evento = await asyncio.to_thread(_insertar)
            return ResultadoEspejo.OK, evento.get("id")
        except Exception as exc:
            if self._es_error_de_token(exc):
                self._marcar_token_muerto()
                return ResultadoEspejo.DESACTIVADO, None
            logger.warning("No pude crear el evento en Calendar: %s", exc)
            return ResultadoEspejo.FALLO, None

    async def borrar_evento(self, event_id: str) -> None:
        """Best effort: un evento espejo huérfano no es un problema."""
        if not self.habilitado:
            return

        def _borrar():
            self._get_service().events().delete(
                calendarId=self._config.gcal_calendar_id, eventId=event_id
            ).execute()

        try:
            await asyncio.to_thread(_borrar)
        except Exception as exc:
            if self._es_error_de_token(exc):
                self._marcar_token_muerto()
            else:
                logger.warning("No pude borrar el evento %s de Calendar: %s", event_id, exc)
