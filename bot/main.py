"""Punto de entrada del bot: arma la aplicación, recupera la agenda y hace polling."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from . import handlers
from .config import cargar_config
from .db import Database
from .gcal import CalendarMirror
from .nlp import NLP
from .scheduler import ReminderScheduler

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    """Corre con el event loop ya andando, antes de empezar el polling."""
    scheduler = ReminderScheduler(app.bot, app.bot_data["db"], app.bot_data["config"])
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    await scheduler.recuperar()
    gcal: CalendarMirror = app.bot_data["gcal"]
    logger.info(
        "Bot listo. Espejo de Google Calendar: %s",
        "activo" if gcal.habilitado else "apagado (sin token.json)",
    )


def main() -> None:
    config = cargar_config()

    db = Database(config.db_path)
    db.init()

    app = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .post_init(_post_init)
        .build()
    )
    app.bot_data["config"] = config
    app.bot_data["db"] = db
    app.bot_data["nlp"] = NLP(config)
    app.bot_data["gcal"] = CalendarMirror(config)

    # La whitelist corre antes que cualquier otro handler (group -1).
    app.add_handler(TypeHandler(Update, handlers.whitelist), group=-1)

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("lista", handlers.cmd_lista))
    app.add_handler(CallbackQueryHandler(handlers.callback_confirmacion, pattern=r"^conf:"))
    app.add_handler(CallbackQueryHandler(handlers.callback_borrar, pattern=r"^del:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.mensaje_texto))
    app.add_handler(MessageHandler(filters.VOICE, handlers.nota_de_voz))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
