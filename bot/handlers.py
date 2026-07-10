"""Handlers de Telegram: whitelist, comandos, pedidos por texto y voz, confirmación."""

import logging
import uuid
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationHandlerStop, ContextTypes

from .formatting import describir_recurrencia, formatear_fecha
from .gcal import ResultadoEspejo
from .nlp import Interpretacion, NLPError

logger = logging.getLogger(__name__)

AYUDA = (
    "Soy tu bot de recordatorios 🤖\n\n"
    "Decime (por texto o audio) qué querés que te recuerde y cuándo. Ejemplos:\n"
    "• «recordame llamar al médico mañana a las 10»\n"
    "• «recordame sacar la basura todos los lunes a las 8»\n\n"
    "También podés mandarme una foto 📸 (una invitación, un cronograma de "
    "exámenes) y te propongo los eventos que encuentre.\n\n"
    "Comandos:\n"
    "/lista — ver y cancelar recordatorios activos"
)

MENSAJE_SIN_SERVICIO = (
    "😕 No pude interpretar tu pedido en este momento (falló el servicio de "
    "lenguaje). Tus recordatorios ya guardados siguen funcionando. Probá de nuevo en un rato."
)


# --- Control de acceso -----------------------------------------------------

async def whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Corre antes que todo (group=-1): ignora en silencio a cualquier otro chat."""
    config = context.bot_data["config"]
    chat = update.effective_chat
    if chat is None or chat.id != config.allowed_chat_id:
        if chat is not None:
            logger.info("Update ignorado de chat no autorizado: %s", chat.id)
        raise ApplicationHandlerStop


# --- Comandos ---------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("¡Hola! 👋\n\n" + AYUDA)


async def cmd_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto, teclado = _render_lista(context)
    await update.message.reply_text(texto, reply_markup=teclado)


def _render_lista(context: ContextTypes.DEFAULT_TYPE):
    db = context.bot_data["db"]
    activos = db.activos()
    if not activos:
        return "No tenés recordatorios activos. 📭", None

    lineas = ["📋 Tus recordatorios activos:\n"]
    botones = []
    for i, rec in enumerate(activos, start=1):
        cuando = datetime.fromisoformat(rec["proxima_ejecucion"])
        linea = f"{i}. {rec['texto']} — {formatear_fecha(cuando)}"
        if rec["recurrencia"]:
            linea += f" ({describir_recurrencia(rec['recurrencia'], cuando)})"
        lineas.append(linea)
        botones.append(
            InlineKeyboardButton(f"🗑 {i}", callback_data=f"del:{rec['id']}")
        )
    filas = [botones[i : i + 4] for i in range(0, len(botones), 4)]
    lineas.append("\nTocá 🗑 para cancelar uno.")
    return "\n".join(lineas), InlineKeyboardMarkup(filas)


async def callback_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    reminder_id = int(query.data.split(":", 1)[1])

    db = context.bot_data["db"]
    rec = db.obtener(reminder_id)
    if rec is not None and rec["estado"] == "activo":
        db.cambiar_estado(reminder_id, "cancelado")
        context.bot_data["scheduler"].cancelar(reminder_id)
        if rec["gcal_event_id"]:
            await context.bot_data["gcal"].borrar_evento(rec["gcal_event_id"])

    texto, teclado = _render_lista(context)
    await query.edit_message_text(texto, reply_markup=teclado)


# --- Pedidos (texto y voz) --------------------------------------------------

async def mensaje_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _procesar_pedido(update, context, update.message.text)


async def nota_de_voz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    nlp = context.bot_data["nlp"]
    try:
        archivo = await update.message.voice.get_file()
        audio = bytes(await archivo.download_as_bytearray())
        transcripcion = await nlp.transcribir(audio)
    except NLPError:
        await update.message.reply_text(
            "😕 No pude procesar el audio en este momento. Probá de nuevo o escribime el pedido."
        )
        return
    except Exception:
        logger.exception("Fallo descargando la nota de voz")
        await update.message.reply_text(
            "😕 No pude descargar el audio. Probá de nuevo."
        )
        return

    if not transcripcion:
        await update.message.reply_text(
            "No entendí nada en el audio 🙉. Probá de nuevo o escribime el pedido."
        )
        return

    await update.message.reply_text(f"🎙 Entendí: «{transcripcion}»")
    await _procesar_pedido(update, context, transcripcion)


# --- Fotos (invitaciones, cronogramas) ---------------------------------------

async def foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    nlp = context.bot_data["nlp"]
    try:
        # La última variante es la de mayor resolución que ofrece Telegram.
        archivo = await update.message.photo[-1].get_file()
        imagen = bytes(await archivo.download_as_bytearray())
    except Exception:
        logger.exception("Fallo descargando la foto")
        await update.message.reply_text("😕 No pude descargar la foto. Probá de nuevo.")
        return

    try:
        eventos, omitidos = await nlp.interpretar_imagen(imagen, update.message.caption)
    except NLPError:
        await update.message.reply_text(MENSAJE_SIN_SERVICIO)
        return

    # Una foto nueva reemplaza las tarjetas de imagen anteriores no respondidas.
    await _reemplazar_tarjetas_imagen(update, context)

    if not eventos:
        lineas = ["🔍 No encontré eventos con fecha en la imagen."]
        if omitidos:
            lineas.append("⚠️ Vi mencionados, pero sin fecha clara: " + "; ".join(omitidos))
        await update.message.reply_text("\n".join(lineas))
        return

    if len(eventos) > 1:
        await update.message.reply_text(
            f"📸 Encontré {len(eventos)} eventos en la imagen. Confirmá cada uno:"
        )

    pendientes = {}
    for interp in eventos:
        token, tarjeta, teclado = _armar_tarjeta(interp)
        msg = await update.message.reply_text(tarjeta, reply_markup=teclado)
        pendientes[token] = {
            "token": token,
            "mensaje": interp.mensaje,
            "fecha_iso": interp.fecha_hora.isoformat(),
            "rrule": interp.rrule,
            "msg_id": msg.message_id,
        }
    context.user_data["pendientes_imagen"] = pendientes

    if omitidos:
        await update.message.reply_text(
            "⚠️ No pude ubicar fecha para: " + "; ".join(omitidos)
        )


async def _reemplazar_tarjetas_imagen(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Deja inertes las tarjetas de imagen previas, editando sus mensajes."""
    viejas = context.user_data.pop("pendientes_imagen", None) or {}
    for propuesta in viejas.values():
        if not propuesta.get("msg_id"):
            continue
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=propuesta["msg_id"],
                text="↩️ Reemplazado por un pedido más nuevo.",
            )
        except Exception:
            pass


MAX_TURNOS_HILO = 6


def _contexto_pendiente(context: ContextTypes.DEFAULT_TYPE) -> list:
    """Si hay una tarjeta esperando confirmación, la conversación que la produjo
    sirve de contexto para interpretar correcciones («que sea a las 10»).
    Los datos exactos van en un turno system con instrucción imperativa: colgados
    del turno del asistente, el LLM los ignoraba según la redacción del usuario."""
    pendiente = context.user_data.get("pendiente") or {}
    if pendiente.get("texto_origen") and pendiente.get("tarjeta"):
        return [
            {"role": "user", "content": pendiente["texto_origen"]},
            {"role": "assistant", "content": pendiente["tarjeta"]},
            {
                "role": "system",
                "content": (
                    "Hay una propuesta de recordatorio pendiente de confirmación: "
                    f'mensaje="{pendiente["mensaje"]}", '
                    f'fecha_hora_iso="{pendiente["fecha_iso"]}", '
                    f'recurrencia_rrule={pendiente["rrule"] or "null"}. '
                    "Si el usuario pide un cambio, respondé el recordatorio COMPLETO: "
                    "copiá estos valores y modificá SOLO lo que pidió cambiar."
                ),
            },
        ]
    return []


async def _procesar_pedido(
    update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str
) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    nlp = context.bot_data["nlp"]
    # Un hilo de aclaración en curso ya trae la conversación más reciente;
    # si no hay, una tarjeta pendiente aporta su propio contexto.
    hilo = context.user_data.get("hilo") or _contexto_pendiente(context)
    try:
        interp: Interpretacion = await nlp.interpretar(texto, historial=hilo)
    except NLPError:
        await update.message.reply_text(MENSAJE_SIN_SERVICIO)
        return

    if not interp.es_recordatorio:
        # La respuesta no vino al caso: el hilo de aclaración muere acá.
        # La tarjeta pendiente (si hay) queda intacta y sigue siendo confirmable.
        context.user_data.pop("hilo", None)
        await update.message.reply_text(AYUDA)
        return

    if interp.aclaracion:
        hilo = hilo + [
            {"role": "user", "content": texto},
            {"role": "assistant", "content": interp.aclaracion},
        ]
        context.user_data["hilo"] = hilo[-MAX_TURNOS_HILO:]
        await update.message.reply_text("🤔 " + interp.aclaracion)
        return

    context.user_data.pop("hilo", None)
    await _mostrar_confirmacion(update, context, interp, texto)


def _armar_tarjeta(interp: Interpretacion):
    """Tarjeta de confirmación con su token y teclado. Formato compartido por
    las propuestas de texto/voz y las de imagen."""
    token = uuid.uuid4().hex[:8]
    lineas = [
        "📋 Nuevo recordatorio\n",
        f"📝 {interp.mensaje}",
        f"🗓 {formatear_fecha(interp.fecha_hora)}",
    ]
    if interp.rrule:
        lineas.append(f"🔁 {describir_recurrencia(interp.rrule, interp.fecha_hora)}")
    lineas.append("\n¿Lo confirmo?")
    teclado = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirmar", callback_data=f"conf:si:{token}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"conf:no:{token}"),
        ]]
    )
    return token, "\n".join(lineas), teclado


async def _mostrar_confirmacion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    interp: Interpretacion,
    texto_origen: str,
) -> None:
    # Un pedido nuevo reemplaza al pendiente anterior (la tarjeta vieja queda inerte).
    anterior = context.user_data.get("pendiente")
    if anterior and anterior.get("msg_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=anterior["msg_id"],
                text="↩️ Reemplazado por un pedido más nuevo.",
            )
        except Exception:
            pass

    token, tarjeta, teclado = _armar_tarjeta(interp)
    msg = await update.message.reply_text(tarjeta, reply_markup=teclado)
    context.user_data["pendiente"] = {
        "token": token,
        "mensaje": interp.mensaje,
        "fecha_iso": interp.fecha_hora.isoformat(),
        "rrule": interp.rrule,
        "msg_id": msg.message_id,
        "texto_origen": texto_origen,
        "tarjeta": tarjeta,
    }


async def _confirmar_propuesta(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, propuesta: dict
) -> str:
    """Persiste, programa y espeja una propuesta confirmada. Devuelve el texto
    de respuesta. Camino común a las tarjetas de texto/voz y de imagen."""
    db = context.bot_data["db"]
    scheduler = context.bot_data["scheduler"]
    gcal = context.bot_data["gcal"]

    fecha = datetime.fromisoformat(propuesta["fecha_iso"])
    reminder_id = db.crear(
        chat_id=chat_id,
        texto=propuesta["mensaje"],
        proxima_ejecucion=propuesta["fecha_iso"],
        recurrencia=propuesta["rrule"],
    )
    scheduler.programar(reminder_id, fecha)

    lineas = [f"✅ Listo. Te lo recuerdo el {formatear_fecha(fecha)}."]
    if propuesta["rrule"]:
        lineas.append(
            f"🔁 Se repite: {describir_recurrencia(propuesta['rrule'], fecha)}"
        )

    resultado, event_id = await gcal.crear_evento(
        propuesta["mensaje"], fecha, propuesta["rrule"]
    )
    if resultado == ResultadoEspejo.OK:
        db.guardar_gcal_event_id(reminder_id, event_id)
        lineas.append("📅 Anotado también en Google Calendar.")
    elif resultado == ResultadoEspejo.FALLO:
        lineas.append(
            "⚠️ No pude reflejarlo en Google Calendar (el recordatorio funciona igual)."
        )
    elif gcal.aviso_token_pendiente:
        gcal.aviso_token_pendiente = False
        lineas.append(
            "⚠️ El acceso a Google Calendar venció: hay que rehacer el login "
            "(ver README). Mientras tanto sigo funcionando sin calendario."
        )

    return "\n".join(lineas)


async def callback_confirmacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    _, accion, token = query.data.split(":", 2)

    # El token puede ser de la propuesta de texto/voz o de una tarjeta de imagen.
    pendiente = context.user_data.get("pendiente")
    if pendiente is not None and pendiente["token"] == token:
        context.user_data.pop("pendiente", None)
        propuesta = pendiente
    else:
        propuesta = (context.user_data.get("pendientes_imagen") or {}).pop(token, None)

    if propuesta is None:
        await query.edit_message_text(
            "Este pedido ya no está vigente. Mandámelo de nuevo si lo querés."
        )
        return

    if accion == "no":
        await query.edit_message_text("❌ Descartado. No guardé nada.")
        return

    texto = await _confirmar_propuesta(context, update.effective_chat.id, propuesta)
    await query.edit_message_text(texto)
