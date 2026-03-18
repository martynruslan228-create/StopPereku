import os, asyncio, logging, requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Логирование в консоль Railway (чтобы видеть ошибки)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ТВОИ ДАННЫЕ ---
TOKEN = "8611892704:AAFO_owIa_COlz57cigbabtMhIeSY7MgS7g"
CHECK_API_KEY = "6598630f185619b6ba68455ad90c610e"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🔍 Перевірка за номером"]]
    await update.message.reply_text(
        "Бот запущений! Натисніть кнопку нижче, щоб перевірити авто.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔍 Перевірка за номером":
        await update.message.reply_text("Надішліть держномер авто (наприклад: AA1111AA):")
        return

    # Если текст не кнопка, значит это номер машины
    number = text.upper().replace(" ", "")
    await update.message.reply_text(f"Шукаю дані для номера {number}...")

    try:
        url = f"https://baza-gai.com.ua/api/v1/catalog/num/{number}"
        headers = {"Accept": "application/json", "X-Api-Key": CHECK_API_KEY}
        
        # Делаем реальный запрос
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Формируем отчет
            res = (
                f"✅ ДАНІ ЗНАЙДЕНО:\n"
                f"🚗 Авто: {data.get('vendor')} {data.get('model')} ({data.get('model_year')})\n"
                f"🎨 Колір: {data.get('color', {}).get('ua')}\n"
                f"⛽ Двигун: {data.get('digits', {}).get('engine')} л.\n"
                f"📝 Операція: {data.get('last_operation', {}).get('ua')}\n"
                f"📅 Дата: {data.get('last_operation', {}).get('date')}"
            )
            await update.message.reply_text(res)
        elif response.status_code == 401:
            await update.message.reply_text("Помилка: Невірний API ключ Baza-GAI.")
        elif response.status_code == 404:
            await update.message.reply_text("Авто не знайдено в базі.")
        else:
            await update.message.reply_text(f"Помилка сервера: {response.status_code}")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Сталася технічна помилка при запиті.")

async def main():
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск
    print("Бот запущен...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
 
