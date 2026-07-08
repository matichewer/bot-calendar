"""Persistencia de recordatorios en SQLite (fuente de verdad del sistema)."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

ESQUEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    texto TEXT NOT NULL,
    proxima_ejecucion TEXT NOT NULL,  -- ISO 8601 con offset
    recurrencia TEXT,                 -- RRULE (RFC 5545) o NULL si es único
    estado TEXT NOT NULL DEFAULT 'activo',  -- activo | completado | cancelado
    gcal_event_id TEXT,
    creado_en TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_reminders_estado ON reminders (estado);
"""


class Database:
    def __init__(self, path: Path):
        self._path = path

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self._conn() as conn:
            conn.executescript(ESQUEMA)

    def crear(
        self,
        chat_id: int,
        texto: str,
        proxima_ejecucion: str,
        recurrencia: Optional[str] = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (chat_id, texto, proxima_ejecucion, recurrencia)"
                " VALUES (?, ?, ?, ?)",
                (chat_id, texto, proxima_ejecucion, recurrencia),
            )
            return cur.lastrowid

    def obtener(self, reminder_id: int) -> Optional[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()

    def activos(self) -> list:
        with self._conn() as conn:
            return conn.execute(
                "SELECT * FROM reminders WHERE estado = 'activo'"
                " ORDER BY proxima_ejecucion"
            ).fetchall()

    def actualizar_proxima(self, reminder_id: int, proxima_ejecucion: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE reminders SET proxima_ejecucion = ? WHERE id = ?",
                (proxima_ejecucion, reminder_id),
            )

    def cambiar_estado(self, reminder_id: int, estado: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE reminders SET estado = ? WHERE id = ?", (estado, reminder_id)
            )

    def guardar_gcal_event_id(self, reminder_id: int, event_id: Optional[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE reminders SET gcal_event_id = ? WHERE id = ?",
                (event_id, reminder_id),
            )
