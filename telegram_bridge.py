import logging
import os
import re
import json
from io import BytesIO
from datetime import datetime
import time

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import aiohttp
import pytesseract
from PIL import Image

BUTTON_INTENT_MAP = {
    "Sí, otro problema": "/afirmacion",
    "Si, otro problema": "/afirmacion", 
    "No, gracias": "/negacion",

    
    "Sí, ya se solucionó ✅": "/afirmacion",
    "No, sigue el problema ❌": "/negacion",

    
    "Ver más pasos": "/ver_mas_pasos",
    "Levantar reporte": "/levantar_reporte",
    "Generar reporte": "/levantar_reporte",
}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7475824252:AAGXHqXeEKx3IWg6W9WNs4HRaO35NmJIvpY")
RASA_REST_URL = "http://localhost:5005/webhooks/rest/webhook"
LOG_DIR = "logs"
CONV_LOG_PATH = os.path.join(LOG_DIR, "conversation_events.jsonl")
LAST_ACTIVITY = {}
SESSION_TIMEOUT_SECONDS = 600 

def log_conversation_event(event: dict) -> None:
    
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        event = dict(event)
        event["timestamp"] = datetime.utcnow().isoformat()
        with open(CONV_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[CONV-LOG] Error al escribir el log: {e}")


def extract_employee_code_from_text(text: str) -> str | None:
    
    if not text:
        return None

    text_up = text.upper()

    #número de 5 o 6 dígitos aislado
    m = re.search(r"\b(\d{5,6})\b", text)
    if m:
        return m.group(1)
    return None


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def call_rasa(sender_id: str, message: str):
    
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
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username

    text_out = (
        "Hola 👋, soy el asistente de Soporte Técnico. "
        "Escribe tu problema o simplemente 'hola' para empezar."
    )

    await update.message.reply_text(text_out)

    
    log_conversation_event(
        {
            "direction": "bot",
            "user_id": user_id,
            "username": username,
            "text": text_out,
            "chat_id": chat_id,
            "source": "start",
        }
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja cualquier mensaje de texto del usuario."""
    if update.message is None or update.message.text is None:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username
    chat_id = update.effective_chat.id
    user_text = update.message.text
        
    now = time.time()
    last = LAST_ACTIVITY.get(user_id)
    
    if last and now - last > SESSION_TIMEOUT_SECONDS:
        text_expired = (
            "⌛ Tu sesión anterior expiró por inactividad.\n"
            "Iniciaremos una nueva sesión. ¿En qué puedo ayudarte?"
        )
        await context.bot.send_message(chat_id=chat_id, text=text_expired)

        
        log_conversation_event(
            {
                "direction": "bot",
                "user_id": user_id,
                "username": username,
                "text": text_expired,
                "chat_id": chat_id,
                "session_event": "expired_session_notice",
            }
        )
        
        await call_rasa(str(chat_id), "/restart")

    
    LAST_ACTIVITY[user_id] = now
    
    logger.info(f"Mensaje de Telegram {chat_id}: {user_text}")
    text_stripped = user_text.strip()
    message_for_rasa = BUTTON_INTENT_MAP.get(text_stripped, user_text)
    responses = await call_rasa(str(chat_id), message_for_rasa)

    if not responses:
        text_out = (
            "Lo siento, hubo un problema al procesar tu mensaje en el servidor de soporte."
        )
        await update.message.reply_text(text_out)

        
        log_conversation_event(
            {
                "direction": "bot",
                "user_id": user_id,
                "username": username,
                "text": text_out,
                "chat_id": chat_id,
                "error": "rasa_no_response",
            }
        )
        return

    for r in responses:
        text = r.get("text")
        buttons = r.get("buttons")
        image = r.get("image")

        
        if image:
            logger.info(f"Enviando imagen al chat {chat_id}: {image}")
            await context.bot.send_photo(chat_id=chat_id, photo=image)

            
            log_conversation_event(
                {
                    "direction": "bot",
                    "user_id": user_id,
                    "username": username,
                    "image": image,
                    "chat_id": chat_id,
                    "raw_rasa_message": r,
                }
            )

        
        if buttons:
            keyboard_rows = []
            row = []
            for i, b in enumerate(buttons, start=1):
                title = b.get("title") or b.get("payload") or "Opción"
                row.append(KeyboardButton(title))
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

            text_out = text or "Selecciona una opción:"

            await update.message.reply_text(
                text_out,
                reply_markup=reply_markup,
            )

            
            log_conversation_event(
                {
                    "direction": "bot",
                    "user_id": user_id,
                    "username": username,
                    "text": text_out,
                    "chat_id": chat_id,
                    "buttons": [b.get("title") for b in buttons],
                    "raw_rasa_message": r,
                }
            )

        
        elif text:
            text_out = text
            await update.message.reply_text(text_out)

            
            log_conversation_event(
                {
                    "direction": "bot",
                    "user_id": user_id,
                    "username": username,
                    "text": text_out,
                    "chat_id": chat_id,
                    "raw_rasa_message": r,
                }
            )


async def ocr_from_telegram_photo(file_id: str, context: ContextTypes.DEFAULT_TYPE) -> str:
  
    bot = context.bot

    # Obtener el archivo desde Telegram
    file = await bot.get_file(file_id)
    file_bytes = await file.download_as_bytearray()

    # Abrir la imagen en memoria
    image = Image.open(BytesIO(file_bytes))

    # Ejecutar OCR con Tesseract
    text = pytesseract.image_to_string(image, lang="spa")
    return text


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if update.message is None or not update.message.photo:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username

    logger.info(f"Foto recibida de {chat_id}. Intentando OCR para carnet...")

    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    log_conversation_event(
        {
            "direction": "user",
            "user_id": user_id,
            "username": username,
            "photo_file_id": file_id,
            "chat_id": chat_id,
            "type": "photo",
        }
    )

    
    try:
        ocr_text = await ocr_from_telegram_photo(file_id, context)
        logger.info(f"OCR detectó el texto: {ocr_text!r}")

        employee_code = extract_employee_code_from_text(ocr_text)

        if not employee_code:
            text_out = (
                "He recibido la foto, pero no pude leer claramente tu código de empleado en el carnet. "
                "Por favor envíame tu código en texto (por ejemplo: 123456)."
            )
            await update.message.reply_text(text_out)

            
            log_conversation_event(
                {
                    "direction": "bot",
                    "user_id": user_id,
                    "username": username,
                    "text": text_out,
                    "chat_id": chat_id,
                    "context": "ocr_no_employee_code",
                }
            )
            return

        text_out = (
            f"He detectado tu código de empleado: {employee_code}. "
            "Lo estoy enviando al asistente de soporte para validar tu identidad..."
        )
        await update.message.reply_text(text_out)

        
        log_conversation_event(
            {
                "direction": "bot",
                "user_id": user_id,
                "username": username,
                "text": text_out,
                "chat_id": chat_id,
                "context": "ocr_employee_code_detected",
                "employee_code": employee_code,
            }
        )

        
        simulated_text = f"aqui esta mi carnet {employee_code}"

        responses = await call_rasa(str(chat_id), simulated_text)

        if not responses:
            text_out = (
                "Ocurrió un problema al comunicarme con el servidor de soporte."
            )
            await update.message.reply_text(text_out)

            
            log_conversation_event(
                {
                    "direction": "bot",
                    "user_id": user_id,
                    "username": username,
                    "text": text_out,
                    "chat_id": chat_id,
                    "error": "rasa_no_response_ocr",
                }
            )
            return

        for r in responses:
            text = r.get("text")
            buttons = r.get("buttons")
            image = r.get("image")

            
            if image:
                logger.info(f"Enviando imagen al chat {chat_id}: {image}")
                await context.bot.send_photo(chat_id=chat_id, photo=image)

                log_conversation_event(
                    {
                        "direction": "bot",
                        "user_id": user_id,
                        "username": username,
                        "image": image,
                        "chat_id": chat_id,
                        "raw_rasa_message": r,
                        "context": "ocr_rasa_response",
                    }
                )

            
            if buttons:
                keyboard_rows = []
                row = []
                for i, b in enumerate(buttons, start=1):
                    title = b.get("title") or b.get("payload") or "Opción"
                    row.append(KeyboardButton(title))
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

                text_out = text or "Selecciona una opción:"

                await update.message.reply_text(
                    text_out,
                    reply_markup=reply_markup,
                )

                log_conversation_event(
                    {
                        "direction": "bot",
                        "user_id": user_id,
                        "username": username,
                        "text": text_out,
                        "chat_id": chat_id,
                        "buttons": [b.get("title") for b in buttons],
                        "raw_rasa_message": r,
                        "context": "ocr_rasa_response",
                    }
                )

            
            elif text:
                text_out = text
                await update.message.reply_text(text_out)

                log_conversation_event(
                    {
                        "direction": "bot",
                        "user_id": user_id,
                        "username": username,
                        "text": text_out,
                        "chat_id": chat_id,
                        "raw_rasa_message": r,
                        "context": "ocr_rasa_response",
                    }
                )

    except Exception as e:
        logger.exception(f"Error procesando foto para OCR: {e}")
        text_out = (
            "Ocurrió un error al procesar la imagen del carnet. "
            "Por favor intenta nuevamente o envía tu código de empleado en texto (E12345)."
        )
        await update.message.reply_text(text_out)

        log_conversation_event(
            {
                "direction": "bot",
                "user_id": user_id,
                "username": username,
                "text": text_out,
                "chat_id": chat_id,
                "error": "ocr_exception",
            }
        )


def main():
    
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith(""):
        raise RuntimeError("Por favor configura TELEGRAM_TOKEN con el token de tu bot.")

    application = Application.builder().token(TELEGRAM_TOKEN).build()    
    application.add_handler(CommandHandler("start", start))
        
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    application.add_handler(
        MessageHandler(filters.PHOTO, handle_photo)
    )

    logger.info("Bot de Telegram iniciado en modo polling.")
    application.run_polling()


if __name__ == "__main__":
    main()
