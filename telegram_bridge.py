import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton

BUTTON_INTENT_MAP = {
    "Sí, otro problema": "/afirmacion",
    "Si, otro problema": "/afirmacion",   # por si acaso sin tilde
    "No, gracias": "/negacion",
}

# ⚙️ CONFIG
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7475824252:AAGXHqXeEKx3IWg6W9WNs4HRaO35NmJIvpY")
RASA_REST_URL = "http://localhost:5005/webhooks/rest/webhook"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def call_rasa(sender_id: str, message: str):
    """Llama al endpoint REST de Rasa y devuelve la lista de respuestas."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            RASA_REST_URL,
            json={"sender": sender_id, "message": message},
        ) as resp:
            if resp.status != 200:
                logger.error(f"Error llamando a Rasa: {resp.status}")
                return []

            try:
                data = await resp.json()
                return data
            except Exception as e:
                logger.exception(f"Error parseando respuesta de Rasa: {e}")
                return []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start en Telegram."""
    chat_id = update.effective_chat.id
    # Podrías mandar un saludo propio o disparar 'hola' hacia Rasa
    await update.message.reply_text(
        "Hola 👋, soy el asistente de Soporte Técnico. Escribe tu problema o simplemente 'hola' para empezar."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja cualquier mensaje de texto del usuario."""
    if update.message is None or update.message.text is None:
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id

    logger.info(f"Mensaje de Telegram {chat_id}: {user_text}")

    # Normalizamos el texto para mapear botones especiales a intents
    text_stripped = user_text.strip()

    # Si el texto coincide con un botón que tiene payload de intent,
    # usamos el intent (ej: "/afirmacion") en lugar del texto visible.
    message_for_rasa = BUTTON_INTENT_MAP.get(text_stripped, user_text)

    # Enviar mensaje a Rasa
    responses = await call_rasa(str(chat_id), message_for_rasa)

    # Enviar todas las respuestas de Rasa al usuario
    if not responses:
        await update.message.reply_text(
            "Lo siento, hubo un problema al procesar tu mensaje en el servidor de soporte."
        )
        return

    for r in responses:
        text = r.get("text")
        buttons = r.get("buttons")

        # Si Rasa devuelve botones, los convertimos a un teclado de Telegram
        if buttons:
            # Construimos una matriz de botones (ej: 2 por fila)
            keyboard_rows = []
            row = []
            for i, b in enumerate(buttons, start=1):
                title = b.get("title") or b.get("payload") or "Opción"
                row.append(KeyboardButton(title))
                # 2 botones por fila (puedes cambiar a 3, etc.)
                if i % 2 == 0:
                    keyboard_rows.append(row)
                    row = []
            if row:
                keyboard_rows.append(row)

            reply_markup = ReplyKeyboardMarkup(
                keyboard_rows,
                resize_keyboard=True,
                one_time_keyboard=True,
            )

            await update.message.reply_text(
                text or "Selecciona una opción:",
                reply_markup=reply_markup,
            )
        elif text:
            await update.message.reply_text(text)

def main():
    """Arranca el bot de Telegram en modo polling."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("AQUI_VA"):
        raise RuntimeError("Por favor configura TELEGRAM_TOKEN con el token de tu bot.")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # /start
    application.add_handler(CommandHandler("start", start))
    # Cualquier texto normal
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Bot de Telegram iniciado en modo polling.")
    application.run_polling()


if __name__ == "__main__":
    main()
