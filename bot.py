import os, asyncio, logging, sqlite3, threading, requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- НАСТРОЙКИ ---
TOKEN = "8611892704:AAFO_owIa_COlz57cigbabtMhIeSY7MgS7g"
CHANNEL_ID = -1003309289000
CHECK_API_KEY = "6598630f185619b6ba68455ad90c610e" # Твой рабочий ключ

# Состояния диалога
(BRAND, MODEL, YEAR, MILEAGE, ENGINE, FUEL, GEARBOX, DESC, PRICE, 
 PHOTO, DISTRICT, CITY, TG_CONTACT, PHONE, CHOOSE_CAR, WAIT_NEW_PRICE, 
 WAIT_CAR_CHECK) = range(17)

def init_db():
    conn = sqlite3.connect("test_ads.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, msg_id INTEGER, 
                       brand TEXT, model TEXT, year TEXT, mileage TEXT, engine TEXT, fuel TEXT, 
                       gearbox TEXT, desc TEXT, price TEXT, district TEXT, city TEXT, 
                       phone TEXT, tg_link TEXT, photo_ids TEXT, full_text TEXT)''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [
        ["➕ Нове оголошення"],
        ["🔍 Перевірка авто"],
        ["💰 Змінити ціну", "🗑 Видалити"]
    ]
    text = "👋 Вітаю! Я допомагаю керувати оголошеннями та перевіряти авто за реєстрами МВС."
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# --- ФУНКЦИЯ ПРОВЕРКИ АВТО (РЕАЛЬНЫЕ ДАННЫЕ) ---
async def ask_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Введіть державний номер авто (наприклад: **AA1111AA**):",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup([["❌ Скасувати"]], resize_keyboard=True)
    )
    return WAIT_CAR_CHECK

async def process_car_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.upper().replace(" ", "")
    if number == "❌ СКАСУВАТИ": return await start(update, context)

    await update.message.reply_text("🔎 Запит до реєстру МВС... Зачекайте.")

    try:
        # Запрос к Baza-GAI
        url = f"https://baza-gai.com.ua/api/v1/catalog/num/{number}"
        headers = {"Accept": "application/json", "X-Api-Key": CHECK_API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Собираем данные из ответа API
            vendor = data.get('vendor', 'Невідомо')
            model = data.get('model', '')
            year = data.get('model_year', 'Невідомо')
            color = data.get('color', {}).get('ua', 'Невідомо')
            engine = data.get('digits', {}).get('engine', 'Не вказано')
            weight = data.get('digits', {}).get('weight', 'Не вказано')
            op_date = data.get('last_operation', {}).get('date', 'Немає дати')
            op_name = data.get('last_operation', {}).get('ua', 'Немає опису')

            report = (
                f"🚘 **Результати для {number}:**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🔹 **Марка/Модель:** {vendor} {model}\n"
                f"📅 **Рік випуску:** {year}\n"
                f"🎨 **Колір:** {color}\n"
                f"⛽ **Двигун:** {engine} л.\n"
                f"⚖️ **Вага:** {weight} кг\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📝 **Остання дія:**\n"
                f"📅 _{op_date}_\n"
                f"ℹ️ {op_name}"
            )
            await update.message.reply_text(report, parse_mode='Markdown')
        elif response.status_code == 404:
            await update.message.reply_text("❌ Авто не знайдено в базі. Перевірте номер.")
        else:
            await update.message.reply_text("⚠️ Помилка сервісу. Можливо, закінчилися ліміти запитів.")
            
    except Exception as e:
        logging.error(f"Car check error: {e}")
        await update.message.reply_text("⚠️ Не вдалося з'єднатися з реєстром. Спробуйте пізніше.")

    return await start(update, context)

# --- РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ---
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = "edit" if "Змінити ціну" in update.message.text else "del"
    context.user_data['mode'] = mode
    conn = sqlite3.connect("test_ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, brand, model, price FROM ads WHERE user_id = ?", (user_id,))
    ads = cursor.fetchall(); conn.close()
    if not ads:
        await update.message.reply_text("❌ У вас ще немає активних оголошень."); return ConversationHandler.END
    car_buttons = [[f"ID:{ad[0]} | {ad[1]} {ad[2]} (${ad[3]})"] for ad in ads]
    car_buttons.append(["❌ Скасувати"])
    txt = "Оберіть авто для зміни ціни:" if mode == "edit" else "Оберіть авто для видалення:"
    await update.message.reply_text(txt, reply_markup=ReplyKeyboardMarkup(car_buttons, resize_keyboard=True))
    return CHOOSE_CAR

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "❌ Скасувати": return await start(update, context)
    try:
        ad_id = choice.split("|")[0].replace("ID:", "").strip()
        conn = sqlite3.connect("test_ads.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, msg_id, photo_ids FROM ads WHERE id = ?", (ad_id,))
        res = cursor.fetchone(); conn.close()
        if res:
            context.user_data['sel_id'], context.user_data['msg_id'], context.user_data['p_ids'] = res
            if context.user_data['mode'] == "del":
                try: await context.bot.delete_message(CHANNEL_ID, res[1])
                except: pass
                conn = sqlite3.connect("test_ads.db"); c = conn.cursor()
                c.execute("DELETE FROM ads WHERE id = ?", (ad_id,)); conn.commit(); conn.close()
                await update.message.reply_text("🗑 Видалено!"); return await start(update, context)
            else:
                await update.message.reply_text("💰 Введіть НОВУ ЦІНУ ($):", reply_markup=ReplyKeyboardRemove()); return WAIT_NEW_PRICE
    except: pass
    return await start(update, context)

async def update_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_price = update.message.text
    ad_id = context.user_data['sel_id']; msg_id = context.user_data['msg_id']
    conn = sqlite3.connect("test_ads.db"); cursor = conn.cursor()
    cursor.execute("SELECT brand, model, year, mileage, engine, fuel, gearbox, desc, district, city, phone, tg_link FROM ads WHERE id = ?", (ad_id,))
    r = cursor.fetchone()
    new_text = (f"🚗 {r[0]} {r[1]} ({r[2]})\n\n🛣 Пробіг: {r[3]} тис. км\n🔹 Об'єм: {r[4]} л.\n"
                f"⛽️ Паливо: {r[5]}\n⚙️ КПП: {r[6]}\n📍 Район: {r[8]}, {r[9]}\n\n"
                f"💰 Ціна: {new_price}$\n\n📞 Тел: {r[10]}\n👤 Контакт: {r[11]}")
    try:
        await context.bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=msg_id, caption=new_text)
        cursor.execute("UPDATE ads SET price = ?, full_text = ? WHERE id = ?", (new_price, new_text, ad_id))
        conn.commit(); await update.message.reply_text("✅ Ціну оновлено!")
    except Exception as e: await update.message.reply_text(f"❌ Помилка: {e}")
    conn.close(); return await start(update, context)

# --- АНКЕТА ---
async def new_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1. Марка авто:", reply_markup=ReplyKeyboardRemove()); return BRAND

async def get_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['brand'] = update.message.text; await update.message.reply_text("2. Модель:"); return MODEL

async def get_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['model'] = update.message.text; await update.message.reply_text("3. Рік випуску:"); return YEAR

async def get_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['year'] = update.message.text; await update.message.reply_text("4. Пробіг (тис. км):"); return MILEAGE

async def get_mileage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mileage'] = update.message.text; await update.message.reply_text("5. Об'єм двигуна (л):"); return ENGINE

async def get_engine(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['engine'] = update.message.text
    kb = [["Бензин", "Дизель"], ["Газ/Бензин", "Гібрид", "Електро"]]
    await update.message.reply_text("6. Паливо:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return FUEL

async def get_fuel(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['fuel'] = update.message.text
    kb = [["Автомат", "Механіка"], ["Робот", "Варіатор"]]
    await update.message.reply_text("7. КПП:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)); return GEARBOX

async def get_gearbox(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['gearbox'] = update.message.text
    await update.message.reply_text("8. Опис авто:", reply_markup=ReplyKeyboardRemove()); return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text; await update.message.reply_text("9. Ціна ($):"); return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['price'] = update.message.text; context.user_data['photos'] = []
    await update.message.reply_text("10. Надішліть фото. Потім натисніть «✅ Готово»:", 
                                   reply_markup=ReplyKeyboardMarkup([["✅ Готово"], ["⏩ Пропустити"]], resize_keyboard=True)); return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["✅ Готово", "⏩ Пропустити"]:
        districts = [["Березівський", "Білгород-Дністровський"], ["Болградський", "Ізмаїльський"], ["Одеський", "Подільський"]]
        await update.message.reply_text("11. Район:", reply_markup=ReplyKeyboardMarkup(districts, resize_keyboard=True)); return DISTRICT
    if update.message.photo: context.user_data['photos'].append(update.message.photo[-1].file_id)
    return PHOTO

async def get_district(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['district'] = update.message.text; await update.message.reply_text("12. Місто:", reply_markup=ReplyKeyboardRemove()); return CITY 

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    context.user_data['city'] = update.message.text
    await update.message.reply_text("13. Посилання на ваш ТГ?", reply_markup=ReplyKeyboardMarkup([["✅ Так", "❌ Ні"]], resize_keyboard=True)); return TG_CONTACT

async def get_tg_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    context.user_data['tg_link'] = f"@{u.username}" if update.message.text == "✅ Так" and u.username else "Приватна особа"
    await update.message.reply_text("14. Номер телефону:", reply_markup=ReplyKeyboardRemove()); return PHONE

async def finish_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data; phone = update.message.text
    caption = (f"🚗 {ud['brand']} {ud['model']} ({ud['year']})\n\n🛣 Пробіг: {ud['mileage']} тис. км\n🔹 Об'єм: {ud['engine']} л.\n"
               f"⛽️ Паливо: {ud['fuel']}\n⚙️ КПП: {ud['gearbox']}\n📍 Район: {ud['district']}, {ud['city']}\n\n"
               f"💰 Ціна: {ud['price']}$\n\n📞 Тел: {phone}\n👤 Контакт: {ud['tg_link']}")
    try:
        photos = ud.get('photos', [])
        if photos:
            msgs = await context.bot.send_media_group(CHANNEL_ID, media=[InputMediaPhoto(p, caption=caption if i==0 else "") for i, p in enumerate(photos)])
            msg_id = msgs[0].message_id
        else:
            msg = await context.bot.send_message(CHANNEL_ID, caption); msg_id = msg.message_id
        conn = sqlite3.connect("test_ads.db"); c = conn.cursor()
        c.execute("INSERT INTO ads (user_id, msg_id, brand, model, year, mileage, engine, fuel, gearbox, desc, price, district, city, phone, tg_link, photo_ids, full_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (update.effective_user.id, msg_id, ud['brand'], ud['model'], ud['year'], ud['mileage'], ud['engine'], ud['fuel'], ud['gearbox'], ud['desc'], ud['price'], ud['district'], ud['city'], phone, ud['tg_link'], ",".join(photos), caption))
        conn.commit(); conn.close(); await update.message.reply_text("✅ Опубліковано!")
    except Exception as e: await update.message.reply_text(f"Помилка: {e}")
    return await start(update, context)

# --- ЗАПУСК ---
class Health(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

async def main():
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), Health).serve_forever(), daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Нове оголошення$"), new_ad),
            MessageHandler(filters.Regex("^🔍 Перевірка авто$"), ask_car_number),
            MessageHandler(filters.Regex("^(💰 Змінити ціну|🗑 Видалити)$"), show_list)
        ],
        states={
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_brand)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_model)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mileage)],
            ENGINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_engine)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fuel)],
            GEARBOX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gearbox)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price)],
            PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, get_photo)],
            DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_district)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            TG_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tg_contact)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_ad)],
            CHOOSE_CAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
            WAIT_NEW_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_price)],
            WAIT_CAR_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_car_check)]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    app.add_handler(conv); app.add_handler(CommandHandler("start", start))
    await app.initialize(); await app.bot.delete_webhook(drop_pending_updates=True)
    await app.start(); await app.updater.start_polling(); await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
 
