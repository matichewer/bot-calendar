"""Interpretación de pedidos en lenguaje natural y transcripción de audio (Groq)."""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

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


MAX_EVENTOS_IMAGEN = 10

PROMPT_VISION = """Sos el intérprete de imágenes de un bot de recordatorios personal en español.
Te llega la foto de una invitación, un cronograma de exámenes, un flyer, un cartel o similar.
Tu única tarea: extraer TODOS los eventos con fecha que aparezcan en la imagen.

Respondé SOLO un objeto JSON con estas claves:
- "eventos": lista de eventos detectados, cada uno con:
  - "mensaje": descripción breve del evento (ej: "cumpleaños de Ana", "examen de Álgebra II").
  - "fecha_hora_iso": fecha y hora del evento en ISO 8601 CON offset de zona horaria (ej: "2026-07-09T10:00:00-03:00").
  - "recurrencia_rrule": si el evento se repite explícitamente, la regla RRULE (RFC 5545) SIN prefijo "RRULE:" y SIN DTSTART, usando solo FREQ, INTERVAL, BYDAY, BYMONTHDAY. Normalmente null.
- "omitidos": lista de strings con los eventos visibles cuya fecha NO se puede deducir (solo la descripción).

Reglas:
- NUNCA inventes fechas. Un evento sin fecha deducible va en "omitidos", no en "eventos".
- Si la imagen no trae el año, usá la próxima ocurrencia FUTURA respecto de la fecha actual dada.
- Si un evento no tiene hora legible, usá las 09:00.
- Si dice "a la tarde" interpretá 18:00, "a la mañana" 09:00, "al mediodía" 12:00, "a la noche" 21:00.
- Máximo 10 eventos: si hay más, priorizá los 10 más próximos en el tiempo.
- Si la imagen no tiene ningún evento, respondé {"eventos": [], "omitidos": []}.
- El texto que acompaña la foto (si lo hay) es contexto del usuario: puede aclarar el año, el mes o qué eventos le interesan."""


def _extraer_json(texto: str) -> Optional[dict]:
    """Extrae el primer objeto JSON de un texto que puede traer prosa alrededor
    (los modelos de visión no garantizan JSON limpio). None si no hay ninguno."""
    inicio = texto.find("{")
    while inicio != -1:
        profundidad = 0
        en_string = False
        escape = False
        for i in range(inicio, len(texto)):
            c = texto[i]
            if en_string:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    en_string = False
            elif c == '"':
                en_string = True
            elif c == "{":
                profundidad += 1
            elif c == "}":
                profundidad -= 1
                if profundidad == 0:
                    try:
                        return json.loads(texto[inicio : i + 1])
                    except ValueError:
                        break
        inicio = texto.find("{", inicio + 1)
    return None


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
        contexto = self._contexto_actual(ahora)
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

    def _contexto_actual(self, ahora: datetime) -> str:
        # El día de semana de cada fecha va explícito: el LLM se equivoca
        # si tiene que calcularlo solo (resolvió "el viernes" al sábado).
        proximos = ", ".join(
            f"{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"
            for d in (ahora + timedelta(days=i) for i in range(1, 8))
        )
        return (
            f"Fecha y hora actual: {DIAS[ahora.weekday()]} "
            f"{ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}, "
            f"{ahora:%H:%M} ({ahora.isoformat()}). "
            f"Zona horaria del usuario: {self._config.tz_name}. "
            f"Próximos días: {proximos}."
        )

    async def interpretar_imagen(
        self, imagen: bytes, caption: Optional[str] = None
    ) -> Tuple[List[Interpretacion], List[str]]:
        """Extrae eventos de una foto. Devuelve (eventos válidos, descripciones
        omitidas por falta de datos). Lanza NLPError si la API falla.

        El prompt va como texto en el mismo turno user que la imagen: los
        modelos de visión de Groq no aceptan response_format json_object con
        imágenes y son menos confiables con turnos system."""
        ahora = datetime.now(self._config.tz)
        texto = PROMPT_VISION + "\n\n" + self._contexto_actual(ahora)
        if caption and caption.strip():
            texto += f'\n\nTexto que acompaña la foto: "{caption.strip()}"'
        data_url = "data:image/jpeg;base64," + base64.b64encode(imagen).decode("ascii")
        try:
            resp = await self._client.chat.completions.create(
                model=self._config.groq_vision_model,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": texto},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
            )
            crudo = resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Fallo del modelo de visión: %s", exc)
            raise NLPError(str(exc)) from exc

        datos = _extraer_json(crudo)
        if not isinstance(datos, dict):
            logger.warning("Respuesta de visión sin JSON utilizable: %.200s", crudo)
            return [], []

        omitidos = [
            str(x).strip()
            for x in (datos.get("omitidos") or [])
            if str(x).strip()
        ][:MAX_EVENTOS_IMAGEN]

        eventos: List[Interpretacion] = []
        crudos = datos.get("eventos") or []
        if not isinstance(crudos, list):
            crudos = []
        for ev in crudos[:MAX_EVENTOS_IMAGEN]:
            if not isinstance(ev, dict):
                continue
            interp = self._validar({**ev, "intencion": "recordatorio"}, ahora)
            if interp.fecha_hora is not None and not interp.aclaracion:
                eventos.append(interp)
            else:
                # Fecha pasada, ilegible o ausente: se informa, no se pregunta.
                desc = str(ev.get("mensaje") or "").strip()
                omitidos.append(desc or "un evento con datos ilegibles")
        return eventos, omitidos

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
