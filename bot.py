async def process_car_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Очистка текста от пробелов и перевод в верхний регистр
    raw_number = update.message.text.upper().replace(" ", "").strip()
    
    if raw_number == "❌СКАСУВАТИ": 
        return await start(update, context)

    # 2. Нормализация (замена кириллицы на латиницу для API)
    symbols = {
        'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E', 'Н': 'H', 
        'І': 'I', 'К': 'K', 'М': 'M', 'О': 'O', 'Р': 'P', 
        'Т': 'T', 'Х': 'X'
    }
    number = "".join(symbols.get(char, char) for char in raw_number)

    await update.message.reply_text(f"🔎 Запит до реєстру для номера {number}...")

    try:
        url = f"https://baza-gai.com.ua/api/v1/catalog/num/{number}"
        headers = {
            "Accept": "application/json", 
            "X-Api-Key": CHECK_API_KEY
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        logging.info(f"API Response for {number}: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            
            # Извлекаем данные с защитой от пустых полей
            vendor = data.get('vendor', 'Невідомо')
            model = data.get('model', '')
            year = data.get('model_year', 'Невідомо')
            color = data.get('color', {}).get('ua', 'Невідомо')
            engine = data.get('digits', {}).get('engine', 'Не вказано')
            
            last_op = data.get('last_operation', {})
            op_date = last_op.get('date', 'Дані відсутні')
            op_name = last_op.get('ua', 'Опис відсутній')

            res = (
                f"✅ **ДАНІ ЗНАЙДЕНО**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🚗 **Авто:** {vendor} {model} ({year})\n"
                f"🎨 **Колір:** {color}\n"
                f"⛽ **Двигун:** {engine} л.\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📝 **Остання операція:**\n"
                f"📅 {op_date}\n"
                f"ℹ️ {op_name}"
            )
            await update.message.reply_text(res, parse_mode='Markdown')
        
        elif response.status_code == 404:
            await update.message.reply_text(f"❌ Номер {number} не знайдено.\nСпробуйте ввести номер іншою мовою або перевірте правильність.")
        
        elif response.status_code == 403:
            await update.message.reply_text("⚠️ Помилка: Ваш API ключ заблоковано або невірний.")
            
        else:
            await update.message.reply_text(f"⚠️ Помилка сервера (Код: {response.status_code}). Спробуйте пізніше.")

    except Exception as e:
        logging.error(f"Car check error: {e}")
        await update.message.reply_text("⚠️ Технічна помилка при з'єднанні з базою.")

    return await start(update, context)
    
