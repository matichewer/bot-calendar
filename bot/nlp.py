"""Interpretación de pedidos en lenguaje natural y transcripción de audio (Groq)."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from dateutil.rrule import rrulestr
from groq import AsyncGroq

from .config import Config
from .formatting import DIAS, MESES

logger = logging.getLogger(__name__)


class NLPError(Exception):
    """Falla al hablar con la API de Groq (red, rate limit, respuesta inválida)."""


@dataclass
class Interpretacion:
    """Resultado del parseo. Exactamente uno de estos caminos aplica:
    - aclaracion: hay que preguntarle algo al usuario
    - es_recordatorio False: el mensaje no pedía un recordatorio
    - si no: mensaje + fecha_hora (+ rrule opcional) listos para confirmar
    """

    es_recordatorio: bool
    mensaje: str = ""
    fecha_hora: Optional[datetime] = None
    rrule: Optional[str] = None
    aclaracion: Optional[str] = None


PROMPT_SISTEMA = """Sos el intérprete de un bot de recordatorios personal en español.
Tu única tarea: extraer de un mensaje qué hay que recordar y cuándo.

Respondé SOLO un objeto JSON con estas claves:
- "intencion": "recordatorio" si el mensaje pide recordar algo, "otro" si no.
- "mensaje": el texto a recordar, breve y en infinitivo si es natural (ej: "llamar al médico"). Sin la palabra "recordar".
- "fecha_hora_iso": fecha y hora del PRIMER aviso, en ISO 8601 CON offset de zona horaria (ej: "2026-07-09T10:00:00-03:00"). Para recurrentes, la primera ocurrencia futura.
- "recurrencia_rrule": si el pedido se repite, la regla RRULE (RFC 5545) SIN el prefijo "RRULE:" y SIN DTSTART, usando solo FREQ, INTERVAL, BYDAY, BYMONTHDAY. NO uses BYHOUR ni BYMINUTE: la hora sale de fecha_hora_iso. Si no se repite, null.
- "aclaracion": si falta información esencial (fecha u hora imposibles de deducir) o el pedido es ambiguo, una pregunta corta en español para el usuario. Si no hace falta, null.

Reglas:
- NUNCA inventes fecha ni hora. Si el usuario no dio hora y no es deducible, preguntá con "aclaracion".
- fecha_hora_iso debe ser FUTURA respecto de la fecha/hora actual dada.
- "mañana", "el viernes", "en dos horas", etc. se resuelven con la fecha/hora actual dada.
- Si dice solo "a la tarde" interpretá 18:00, "a la mañana" 09:00, "al mediodía" 12:00, "a la noche" 21:00.
- Si intencion es "otro", el resto va null/vacío.
- Si la conversación tiene mensajes previos, son una de dos situaciones:
  a) Hiciste una pregunta de aclaración: el último mensaje del usuario la responde. Combiná el pedido original con la respuesta en UN solo pedido.
  b) Propusiste un recordatorio que espera confirmación (el mensaje con "¿Lo confirmo?"): si el usuario pide un cambio («que sea a las 10», «mejor el jueves»), devolvé el recordatorio COMPLETO corregido, conservando los campos que no pidió cambiar. Si en cambio pide recordar otra cosa, interpretalo como pedido nuevo.
  En ambos casos, usá "otro" solo si el último mensaje no tiene ninguna relación con recordatorios.

Ejemplos:
Usuario: "recordame sacar la basura todos los lunes a las 8" (hoy jueves 2026-07-09)
{"intencion":"recordatorio","mensaje":"sacar la basura","fecha_hora_iso":"2026-07-13T08:00:00-03:00","recurrencia_rrule":"FREQ=WEEKLY;BYDAY=MO","aclaracion":null}

Usuario: "recordame el cumpleaños de Ana"
{"intencion":"recordatorio","mensaje":"cumpleaños de Ana","fecha_hora_iso":null,"recurrencia_rrule":null,"aclaracion":"¿Qué día es el cumpleaños de Ana y a qué hora querés que te avise?"}

Usuario: "hola, qué tal?"
{"intencion":"otro","mensaje":"","fecha_hora_iso":null,"recurrencia_rrule":null,"aclaracion":null}"""


class NLP:
    def __init__(self, config: Config):
        self._config = config
        self._client = AsyncGroq(api_key=config.groq_api_key)

    async def interpretar(
        self, texto: str, historial: Optional[List[dict]] = None
    ) -> Interpretacion:
        """Interpreta un pedido. `historial` son turnos previos de una aclaración
        en curso ({role, content}). Lanza NLPError si la API falla."""
        ahora = datetime.now(self._config.tz)
        # El día de semana de cada fecha va explícito: el LLM se equivoca
        # si tiene que calcularlo solo (resolvió "el viernes" al sábado).
        proximos = ", ".join(
            f"{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"
            for d in (ahora + timedelta(days=i) for i in range(1, 8))
        )
        contexto = (
            f"Fecha y hora actual: {DIAS[ahora.weekday()]} "
            f"{ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}, "
            f"{ahora:%H:%M} ({ahora.isoformat()}). "
            f"Zona horaria del usuario: {self._config.tz_name}. "
            f"Próximos días: {proximos}."
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self._config.groq_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": PROMPT_SISTEMA},
                    {"role": "system", "content": contexto},
                    *(historial or []),
                    {"role": "user", "content": texto},
                ],
            )
            datos = json.loads(resp.choices[0].message.content)
        except Exception as exc:
            logger.warning("Fallo del LLM: %s", exc)
            raise NLPError(str(exc)) from exc

        return self._validar(datos, ahora)

    def _validar(self, datos: dict, ahora: datetime) -> Interpretacion:
        """Convierte el JSON del LLM en una Interpretacion segura, sin confiar en él."""
        if datos.get("intencion") != "recordatorio":
            return Interpretacion(es_recordatorio=False)

        if datos.get("aclaracion"):
            return Interpretacion(es_recordatorio=True, aclaracion=str(datos["aclaracion"]))

        mensaje = (datos.get("mensaje") or "").strip()
        crudo = datos.get("fecha_hora_iso")
        if not mensaje or not crudo:
            return Interpretacion(
                es_recordatorio=True,
                aclaracion="No me quedó claro qué recordarte o cuándo. ¿Me lo repetís con fecha y hora?",
            )

        try:
            fecha = datetime.fromisoformat(str(crudo).replace("Z", "+00:00"))
        except ValueError:
            return Interpretacion(
                es_recordatorio=True,
                aclaracion="No pude entender la fecha. ¿Me la repetís? (ej: mañana a las 10)",
            )
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=self._config.tz)
        fecha = fecha.astimezone(self._config.tz)

        if fecha <= ahora:
            return Interpretacion(
                es_recordatorio=True,
                aclaracion="Esa fecha ya pasó. ¿Para cuándo querés el recordatorio?",
            )

        rrule = datos.get("recurrencia_rrule") or None
        if rrule:
            rrule = str(rrule).strip()
            if rrule.upper().startswith("RRULE:"):
                rrule = rrule[6:]
            try:
                rrulestr(rrule, dtstart=fecha)
            except Exception:
                return Interpretacion(
                    es_recordatorio=True,
                    aclaracion="No entendí bien cada cuánto se repite. ¿Me lo aclarás? (ej: todos los lunes)",
                )

        return Interpretacion(
            es_recordatorio=True, mensaje=mensaje, fecha_hora=fecha, rrule=rrule
        )

    async def transcribir(self, audio_ogg: bytes) -> str:
        """Transcribe una nota de voz. Lanza NLPError si la API falla."""
        try:
            resp = await self._client.audio.transcriptions.create(
                file=("nota.ogg", audio_ogg),
                model=self._config.groq_whisper_model,
                language="es",
            )
        except Exception as exc:
            logger.warning("Fallo de transcripción: %s", exc)
            raise NLPError(str(exc)) from exc
        return (resp.text or "").strip()
