async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔍 Перевірка за номером":
        await update.message.reply_text("Надішліть держномер (наприклад: HH6743AC):")
        return

    # 1. Жесткая нормализация номера
    raw = text.upper().replace(" ", "").strip()
    # Карта замены: укр/рус -> латиница
    c = {'А':'A','В':'B','С':'C','Е':'E','Н':'H','І':'I','К':'K','М':'M','О':'O','Р':'P','Т':'T','Х':'X'}
    number = "".join(c.get(char, char) for char in raw)

    await update.message.reply_text(f"🛰 Шукаю {number} через API...")

    try:
        # 2. Формируем запрос
        url = f"https://baza-gai.com.ua/api/v1/catalog/num/{number}"
        # Пробуем передать ключ и в заголовке, и в ссылке (для верности)
        headers = {"Accept": "application/json", "X-Api-Key": CHECK_API_KEY}
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # 3. Если получили данные
        if response.status_code == 200:
            data = response.json()
            vendor = data.get('vendor', 'Невідомо')
            model = data.get('model', '')
            year = data.get('model_year', 'Невідомо')
            
            res = (
                f"✅ **ЗНАЙДЕНО:**\n"
                f"🚗 {vendor} {model} ({year} р.в.)\n"
                f"🎨 Колір: {data.get('color', {}).get('ua', '-')}\n"
                f"⛽ Двигун: {data.get('digits', {}).get('engine', '-')} л.\n"
                f"📅 Реєстрація: {data.get('last_operation', {}).get('date', '-')}"
            )
            await update.message.reply_text(res, parse_mode='Markdown')
        
        # 4. Если ошибка — выводим детали
        else:
            error_details = response.text[:100] # Берем кусочек текста ошибки
            await update.message.reply_text(
                f"❌ Номер {number} не знайдено.\n"
                f"Статус сервера: {response.status_code}\n"
                f"Відповідь: `{error_details}`", 
                parse_mode='Markdown'
            )

    except Exception as e:
        await update.message.reply_text(f"💥 Помилка підключення: {e}")
        
