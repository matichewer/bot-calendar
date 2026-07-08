"""Programación y disparo de recordatorios. SQLite es la única fuente de verdad:
APScheduler solo mantiene en memoria los jobs de los recordatorios activos."""

import logging
import sqlite3
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from dateutil.rrule import rrulestr
from telegram import Bot

from .config import Config
from .db import Database
from .formatting import formatear_fecha

logger = logging.getLogger(__name__)


def proxima_ocurrencia(
    rrule: str, dtstart: datetime, despues_de: datetime
) -> Optional[datetime]:
    """Próxima ocurrencia de la regla estrictamente posterior a `despues_de`."""
    return rrulestr(rrule, dtstart=dtstart).after(despues_de)


class ReminderScheduler:
    def __init__(self, bot: Bot, db: Database, config: Config):
        self._bot = bot
        self._db = db
        self._config = config
        self._scheduler = AsyncIOScheduler(timezone=config.tz)

    def start(self) -> None:
        self._scheduler.start()

    def programar(self, reminder_id: int, cuando: datetime) -> None:
        self._scheduler.add_job(
            self._disparar,
            trigger=DateTrigger(run_date=cuando),
            id=f"reminder-{reminder_id}",
            args=[reminder_id],
            replace_existing=True,
            misfire_grace_time=None,  # si el loop se demoró, dispara igual
        )

    def cancelar(self, reminder_id: int) -> None:
        job = self._scheduler.get_job(f"reminder-{reminder_id}")
        if job:
            job.remove()

    async def _disparar(self, reminder_id: int) -> None:
        rec = self._db.obtener(reminder_id)
        if rec is None or rec["estado"] != "activo":
            return
        await self._enviar(rec, atrasado=False)
        self._avanzar(rec)

    async def _enviar(self, rec: sqlite3.Row, atrasado: bool) -> None:
        prefijo = "⏰ Recordatorio atrasado" if atrasado else "🔔 Recordatorio"
        try:
            await self._bot.send_message(
                chat_id=rec["chat_id"], text=f"{prefijo}:\n{rec['texto']}"
            )
        except Exception:
            logger.exception("No pude enviar el recordatorio %s", rec["id"])

    def _avanzar(self, rec: sqlite3.Row) -> None:
        """Tras disparar: los únicos se completan, los recurrentes se reprograman."""
        if not rec["recurrencia"]:
            self._db.cambiar_estado(rec["id"], "completado")
            return
        ahora = datetime.now(self._config.tz)
        dtstart = datetime.fromisoformat(rec["proxima_ejecucion"])
        siguiente = proxima_ocurrencia(rec["recurrencia"], dtstart, ahora)
        if siguiente is None:  # la regla se agotó (p. ej. UNTIL/COUNT)
            self._db.cambiar_estado(rec["id"], "completado")
            return
        self._db.actualizar_proxima(rec["id"], siguiente.isoformat())
        self.programar(rec["id"], siguiente)

    async def recuperar(self) -> None:
        """Al arrancar: reprograma los activos y despacha lo vencido durante el apagado."""
        ahora = datetime.now(self._config.tz)
        for rec in self._db.activos():
            cuando = datetime.fromisoformat(rec["proxima_ejecucion"])
            if cuando > ahora:
                self.programar(rec["id"], cuando)
                continue
            # Venció con el bot apagado: un solo aviso atrasado.
            await self._enviar(rec, atrasado=True)
            self._avanzar(rec)
        logger.info("Recuperación completa: %d jobs activos", len(self._scheduler.get_jobs()))
