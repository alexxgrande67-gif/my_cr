import os
import json
import logging
import asyncio
from http.server import BaseHTTPRequestHandler
from telegram import Bot, Update
from PIL import Image
from io import BytesIO
from google import genai
from google.genai.errors import APIError

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# --- Получение ключей из переменных окружения Vercel ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# --------------------------------------------------------

# Инициализация Gemini Client
GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
BOT = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

ANALYSIS_PROMPT = (
    "Ты — опытный финансовый аналитик... (Текст промпта остается прежним)..." # Используйте текст из предыдущего ответа
)

async def handle_photo(update: Update):
    """Обработка входящего фото и отправка его в Gemini."""
    
    chat_id = update.effective_chat.id
    
    if not update.message or not update.message.photo:
        await BOT.send_message(chat_id=chat_id, text="Пожалуйста, отправьте мне фотографию.")
        return

    # Отправляем сообщение ожидания
    await BOT.send_message(chat_id=chat_id, text="⏳ Анализирую график с помощью Gemini AI...")

    try:
        # Получаем файл фотографии с наибольшим разрешением
        photo_file = await BOT.get_file(update.message.photo[-1].file_id)
        photo_bytes = await photo_file.download_as_bytes()
        
        # Конвертация в объект PIL Image
        img = Image.open(BytesIO(photo_bytes))

        # Отправка фото и промпта в Gemini
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, ANALYSIS_PROMPT]
        )
        
        # Отправка ответа
        analysis_text = response.text
        
        await BOT.send_message(
            chat_id=chat_id,
            text=f"✅ **РЕЗУЛЬТАТ АНАЛИЗА GEMINI AI**:\n\n{analysis_text}",
            parse_mode='Markdown'
        )

    except APIError as e:
        await BOT.send_message(chat_id=chat_id, text=f"❌ Ошибка API Gemini: {e}")
    except Exception as e:
        await BOT.send_message(chat_id=chat_id, text=f"❌ Неизвестная ошибка: {e}")


def handler(request):
    """Основная функция, вызываемая Vercel при получении Webhook."""
    if request.method == "POST":
        try:
            # Vercel передает тело запроса в виде JSON
            data = request.json
            update = Update.de_json(data, BOT)
            
            # Запускаем асинхронную функцию
            asyncio.run(handle_photo(update))
            
            return json.dumps({"status": "ok"}), 200, {"Content-Type": "application/json"}
        except Exception as e:
            logging.error(f"Ошибка обработки Webhook: {e}")
            return json.dumps({"status": "error"}), 500, {"Content-Type": "application/json"}
    
    # Приветственное сообщение для GET-запроса (проверка)
    return f"Telegram Bot Webhook Endpoint. Status: READY. Bot: {BOT is not None}", 200

# Для совместимости с Vercel (используется стандартный паттерн)
from http.server import HTTPServer
from vercel_python import VercelHandler

class WebhookHandler(VercelHandler):
    def do_POST(self):
        # Декорируем стандартный HTTP-обработчик Vercel для нашей функции
        response, status, headers = handler(self)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

# Vercel ищет entry point, который возвращает handler
def api_handler(event, context):
    return handler(event)
