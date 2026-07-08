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


async def _procesar_pedido(
    update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str
) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    nlp = context.bot_data["nlp"]
    try:
        interp: Interpretacion = await nlp.interpretar(texto)
    except NLPError:
        await update.message.reply_text(MENSAJE_SIN_SERVICIO)
        return

    if not interp.es_recordatorio:
        await update.message.reply_text(AYUDA)
        return

    if interp.aclaracion:
        await update.message.reply_text("🤔 " + interp.aclaracion)
        return

    await _mostrar_confirmacion(update, context, interp)


async def _mostrar_confirmacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, interp: Interpretacion
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
    msg = await update.message.reply_text("\n".join(lineas), reply_markup=teclado)
    context.user_data["pendiente"] = {
        "token": token,
        "mensaje": interp.mensaje,
        "fecha_iso": interp.fecha_hora.isoformat(),
        "rrule": interp.rrule,
        "msg_id": msg.message_id,
    }


async def callback_confirmacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    _, accion, token = query.data.split(":", 2)

    pendiente = context.user_data.get("pendiente")
    if pendiente is None or pendiente["token"] != token:
        await query.edit_message_text(
            "Este pedido ya no está vigente. Mandámelo de nuevo si lo querés."
        )
        return

    context.user_data.pop("pendiente", None)

    if accion == "no":
        await query.edit_message_text("❌ Descartado. No guardé nada.")
        return

    db = context.bot_data["db"]
    scheduler = context.bot_data["scheduler"]
    gcal = context.bot_data["gcal"]

    fecha = datetime.fromisoformat(pendiente["fecha_iso"])
    reminder_id = db.crear(
        chat_id=update.effective_chat.id,
        texto=pendiente["mensaje"],
        proxima_ejecucion=pendiente["fecha_iso"],
        recurrencia=pendiente["rrule"],
    )
    scheduler.programar(reminder_id, fecha)

    lineas = [f"✅ Listo. Te lo recuerdo el {formatear_fecha(fecha)}."]
    if pendiente["rrule"]:
        lineas.append(
            f"🔁 Se repite: {describir_recurrencia(pendiente['rrule'], fecha)}"
        )

    resultado, event_id = await gcal.crear_evento(
        pendiente["mensaje"], fecha, pendiente["rrule"]
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

    await query.edit_message_text("\n".join(lineas))
