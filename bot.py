#!/usr/bin/env python3
"""
Telegram бот "Генератор КП"
Финальная версия: защита от дублей + OCR + поддержка альбомов
"""

import os
import logging
import time
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from parser import CarDescriptionParser
from sheets_logger import sheets_logger

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Состояния FSM
class KPStates(StatesGroup):
    waiting_description = State()
    waiting_screenshot = State()
    editing_card = State()
    editing_field = State()
    waiting_price = State()
    waiting_price_note = State()
    waiting_photos = State()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Белый список
ALLOWED_USERS = []

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Защита от дублей сообщений
last_message_tracker = {}
DUPLICATE_TIMEOUT = 2.0

# Хранилище для альбомов
album_storage = {}


def is_duplicate_message(user_id: int, text: str) -> bool:
    """Проверяет, является ли сообщение дублем"""
    current_time = time.time()
    
    if user_id in last_message_tracker:
        last_data = last_message_tracker[user_id]
        time_diff = current_time - last_data['time']
        
        if time_diff < DUPLICATE_TIMEOUT and last_data['text'] == text:
            logger.info(f"Duplicate message detected from user {user_id}")
            return True
    
    last_message_tracker[user_id] = {
        'text': text,
        'time': current_time
    }
    
    return False


# ==================== КЛАВИАТУРЫ ====================

def get_main_menu():
    """Главное меню"""
    keyboard = [
        [KeyboardButton(text="📝 Создать КП (текст)")],
        [KeyboardButton(text="📸 Создать КП (скриншот)")],
        [KeyboardButton(text="📖 Инструкция"), KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_edit_card_kb():
    """Кнопки редактирования карточки"""
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Название", callback_data="edit_title"),
            InlineKeyboardButton(text="📅 Год", callback_data="edit_year"),
        ],
        [
            InlineKeyboardButton(text="🚗 Привод", callback_data="edit_drive"),
            InlineKeyboardButton(text="⚙️ Двигатель", callback_data="edit_engine"),
        ],
        [
            InlineKeyboardButton(text="🔧 Коробка", callback_data="edit_gearbox"),
            InlineKeyboardButton(text="🎨 Цвет", callback_data="edit_color"),
        ],
        [
            InlineKeyboardButton(text="📊 Пробег", callback_data="edit_mileage"),
        ],
        [
            InlineKeyboardButton(text="📋 Спецификация", callback_data="edit_spec"),
        ],
        [
            InlineKeyboardButton(text="✅ Всё верно → Указать цену", callback_data="proceed_price"),
        ],
        [
            InlineKeyboardButton(text="🔄 Начать заново", callback_data="reset_start"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_price_note_kb():
    """Кнопки выбора типа цены"""
    keyboard = [
        [InlineKeyboardButton(text="💼 С НДС", callback_data="price_note_ндс")],
        [InlineKeyboardButton(text="💵 Без НДС", callback_data="price_note_безндс")],
        [InlineKeyboardButton(text="💰 Наличные", callback_data="price_note_наличные")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_photos_kb(photos_count: int):
    """Кнопки загрузки фото"""
    keyboard = []
    
    if photos_count >= 3:
        keyboard.append([
            InlineKeyboardButton(text="✅ Готово (создать PDF)", callback_data="photos_done")
        ])
    
    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Сбросить фото", callback_data="reset_photos")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_car_card(data: dict, show_price: bool = False) -> str:
    """Форматирует карточку автомобиля"""
    lines = ["📋 **Карточка автомобиля:**\n"]
    
    lines.append(f"📝 **Название:** {data.get('title') or '❓ Не указано'}")
    lines.append(f"📅 **Год:** {data.get('year') or '❓ Не указан'}")
    lines.append(f"🚗 **Привод:** {data.get('drive') or '❓ Не указан'}")
    lines.append(f"⚙️ **Двигатель:** {data.get('engine_short') or '❓ Не указан'}")
    lines.append(f"🔧 **Коробка:** {data.get('gearbox') or '❓ Не указана'}")
    lines.append(f"🎨 **Цвет:** {data.get('color') or '❓ Нужно указать'}")
    
    mileage = data.get('mileage_km')
    if mileage is not None:
        if mileage == 0:
            lines.append(f"📊 **Пробег:** Новый автомобиль")
        else:
            lines.append(f"📊 **Пробег:** {mileage:,} км".replace(',', ' '))
    else:
        lines.append(f"📊 **Пробег:** ❓ Нужно указать")
    
    if show_price:
        price = data.get('price_rub')
        if price:
            lines.append(f"💰 **Цена:** {price:,} руб".replace(',', ' '))
            lines.append(f"📝 **Примечание:** {data.get('price_note', 'с НДС')}")
        else:
            lines.append(f"💰 **Цена:** ❓ Будет указана на следующем шаге")
    
    spec_items = data.get('spec_items', [])
    if spec_items:
        lines.append(f"\n📋 **Спецификация** ({len(spec_items)} пунктов):")
        for item in spec_items[:5]:
            lines.append(f"  • {item}")
        if len(spec_items) > 5:
            lines.append(f"  ... и ещё {len(spec_items) - 5} пунктов")
    else:
        lines.append("\n📋 **Спецификация:** пусто")
    
    return "\n".join(lines)


# ==================== ОБРАБОТКА АЛЬБОМОВ ====================

async def process_album(user_id: int, chat_id: int, state: FSMContext):
    """Обрабатывает накопленные фото после задержки"""
    await asyncio.sleep(1.0)  # Ждём 1 секунду после последнего фото
    
    if user_id not in album_storage:
        return
    
    photos = album_storage[user_id]['photos']
    del album_storage[user_id]
    
    if not photos:
        return
    
    try:
        # Скачиваем все фото
        photo_paths = []
        for i, photo_id in enumerate(photos):
            file = await bot.get_file(photo_id)
            photo_path = f"/tmp/screenshot_{user_id}_{i}.jpg"
            await bot.download_file(file.file_path, photo_path)
            photo_paths.append(photo_path)
        
        logger.info(f"Processing {len(photo_paths)} screenshots for user {user_id}")
        
        # OCR на всех фото
        from ocr_service import ocr_image_to_text
        
        all_text = []
        for i, photo_path in enumerate(photo_paths):
            try:
                text = ocr_image_to_text(photo_path)
                all_text.append(text)
                logger.info(f"OCR photo {i+1}/{len(photo_paths)}: {len(text)} chars")
            except Exception as e:
                logger.error(f"OCR error on photo {i+1}: {e}")
        
        # Объединяем весь текст
        combined_text = "\n\n".join(all_text)
        
        logger.info(f"Combined OCR text length: {len(combined_text)} chars")
        logger.info(f"First 300 chars: {combined_text[:300]}...")
        
        # Парсим
        parser = CarDescriptionParser()
        parsed_data = parser.parse(combined_text)
        
        await state.update_data(
            description_text=combined_text,
            car_data=parsed_data,
            photos=[]
        )
        
        card_text = format_car_card(parsed_data, show_price=False)
        
        # Проверяем что пользователь ещё в состоянии ожидания
        current_state = await state.get_state()
        if current_state == KPStates.waiting_screenshot:
            await bot.send_message(
                chat_id,
                f"✅ Обработано {len(photo_paths)} скриншотов!\n\n" + card_text,
                reply_markup=get_edit_card_kb(),
                parse_mode="Markdown"
            )
            await state.set_state(KPStates.editing_card)
            logger.info(f"User {user_id} processed {len(photo_paths)} screenshots successfully")
        
    except Exception as e:
        logger.error(f"Error processing album: {e}", exc_info=True)
        await bot.send_message(
            chat_id,
            "❌ Ошибка при распознавании. Попробуй:\n"
            "• Сделать скриншоты чётче\n"
            "• Увеличить текст на экране\n"
            "• Отправить заново\n\n"
            "Или используй режим \"Текст\".",
            reply_markup=get_main_menu()
        )
        await state.clear()


# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    user_id = message.from_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await message.answer("⛔️ У вас нет доступа к этому боту.")
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return
    
    await state.clear()
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу создать коммерческое предложение (КП) для автомобиля.\n\n"
        "**Два способа работы:**\n"
        "📝 **Текст** - скопируй и вставь описание\n"
        "📸 **Скриншот** - сделай фото характеристик\n\n"
        "Выбери способ:",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    logger.info(f"User {user_id} started bot")


@dp.message(F.text == "📝 Создать КП (текст)")
async def start_create_kp_text(message: types.Message, state: FSMContext):
    """Начало создания КП через текст"""
    await state.clear()
    
    await message.answer(
        "📋 Отлично! Создадим КП через текст.\n\n"
        "**Шаг 1 из 3:** Отправь мне описание автомобиля.\n\n"
        "💡 **Как скопировать с Авито:**\n"
        "1. Открой объявление на Авито\n"
        "2. Выдели всю страницу (Ctrl+A или Cmd+A)\n"
        "3. Скопируй (Ctrl+C или Cmd+C)\n"
        "4. Вставь сюда (Ctrl+V или Cmd+V)\n\n"
        "Бот автоматически найдёт все нужные данные! ✨",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(KPStates.waiting_description)
    logger.info(f"User {message.from_user.id} started creating KP (text mode)")


@dp.message(F.text == "📸 Создать КП (скриншот)")
async def start_create_kp_screenshot(message: types.Message, state: FSMContext):
    """Начало создания КП через скриншот"""
    await state.clear()
    
    await message.answer(
        "📸 Отлично! Создадим КП через скриншот.\n\n"
        "**Шаг 1 из 3:** Отправь скриншоты характеристик.\n\n"
        "💡 **Как сделать:**\n"
        "1. Открой объявление на Авито\n"
        "2. Сделай скриншоты:\n"
        "   • Название, год, цена, пробег\n"
        "   • Характеристики (двигатель, привод, КПП)\n"
        "   • Цвет и дополнительная информация\n"
        "3. Отправь все фото сюда (можно альбомом)\n\n"
        "✨ Бот распознает текст и соберёт всю информацию!",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(KPStates.waiting_screenshot)
    logger.info(f"User {message.from_user.id} started creating KP (screenshot mode)")


@dp.message(F.text == "📖 Инструкция")
async def show_instruction(message: types.Message):
    """Показывает инструкцию"""
    instruction = """📖 **ИНСТРУКЦИЯ**

**📝 Режим "Текст":**

1️⃣ Открой объявление на Авито
2️⃣ Нажми **Ctrl+A** (Windows) или **Cmd+A** (Mac)
3️⃣ Нажми **Ctrl+C** (Windows) или **Cmd+C** (Mac)
4️⃣ Вставь в бота

**📸 Режим "Скриншот":**

1️⃣ Открой объявление на Авито
2️⃣ Сделай несколько скриншотов:
   • Название, год, цена
   • Характеристики (двигатель, КПП, привод)
   • Цвет, пробег
3️⃣ Отправь все фото боту (можно альбомом)

✅ **Бот найдёт:**
- Название, год, пробег
- Двигатель, привод, коробку
- Цвет, спецификацию

💡 Можешь отредактировать любые поля!"""
    
    await message.answer(instruction, parse_mode="Markdown")


@dp.message(KPStates.waiting_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания (текстовый режим)"""
    
    # Проверка на дубль
    if is_duplicate_message(message.from_user.id, message.text):
        logger.info(f"Ignoring duplicate message from user {message.from_user.id}")
        return
    
    try:
        parser = CarDescriptionParser()
        description_text = message.text
        parsed_data = parser.parse(description_text)
        
        await state.update_data(
            description_text=description_text,
            car_data=parsed_data,
            photos=[]
        )
        
        card_text = format_car_card(parsed_data, show_price=False)
        
        await message.answer(
            "✅ Описание обработано!\n\n" + card_text,
            reply_markup=get_edit_card_kb(),
            parse_mode="Markdown"
        )
        await state.set_state(KPStates.editing_card)
        logger.info(f"User {message.from_user.id} parsed description successfully")
        
    except Exception as e:
        logger.error(f"Error parsing description: {e}")
        await message.answer(
            "❌ Ошибка при обработке описания. Попробуй ещё раз.",
            reply_markup=get_main_menu()
        )
        await state.clear()


@dp.message(KPStates.waiting_screenshot, F.photo)
async def process_screenshot(message: types.Message, state: FSMContext):
    """Обработка скриншотов (OCR режим) с поддержкой альбомов"""
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    photo_id = message.photo[-1].file_id
    
    # Инициализируем хранилище для пользователя
    if user_id not in album_storage:
        album_storage[user_id] = {
            'photos': [],
            'timer': None,
            'chat_id': chat_id
        }
    
    # Добавляем фото
    album_storage[user_id]['photos'].append(photo_id)
    
    # Отменяем старый таймер
    if album_storage[user_id]['timer']:
        album_storage[user_id]['timer'].cancel()
    
    # Отправляем статус
    photo_count = len(album_storage[user_id]['photos'])
    await message.answer(f"📸 Получено {photo_count} фото... (ожидаю остальные)")
    
    # Запускаем новый таймер (обработка через 1 сек после последнего фото)
    album_storage[user_id]['timer'] = asyncio.create_task(
        process_album(user_id, chat_id, state)
    )


@dp.callback_query(F.data.startswith("edit_"))
async def handle_edit_field(callback: types.CallbackQuery, state: FSMContext):
    """Обработка редактирования полей"""
    field_name = callback.data.replace("edit_", "")
    
    prompts = {
        "title": "Введи название автомобиля:",
        "year": "Введи год выпуска (например: 2024):",
        "drive": "Введи привод (Полный/Передний/Задний):",
        "engine": "Введи описание двигателя (например: 585 л.с., 4.0л, Бензин):",
        "gearbox": "Введи коробку передач (Автомат/Механика/Робот/Вариатор):",
        "color": "Введи цвет автомобиля:",
        "mileage": "Введи пробег в км (только число, или 0 для нового):",
        "spec": "Отправь список пунктов спецификации (каждый пункт с новой строки):",
    }
    
    await callback.message.answer(prompts.get(field_name, "Введи значение:"))
    await state.update_data(editing_field=field_name)
    await state.set_state(KPStates.editing_field)
    await callback.answer()


@dp.message(KPStates.editing_field, F.text)
async def save_edited_field(message: types.Message, state: FSMContext):
    """Сохранение отредактированного поля"""
    try:
        data = await state.get_data()
        field_name = data.get("editing_field")
        car_data = data.get("car_data", {})
        
        field_mapping = {
            "title": "title",
            "year": "year",
            "drive": "drive",
            "engine": "engine_short",
            "gearbox": "gearbox",
            "color": "color",
            "mileage": "mileage_km",
            "spec": "spec_items",
        }
        
        actual_field = field_mapping.get(field_name)
        
        if actual_field:
            if field_name in ["year", "mileage"]:
                try:
                    value = int(message.text.replace(" ", "").replace(",", ""))
                    car_data[actual_field] = value
                except ValueError:
                    await message.answer("⚠️ Пожалуйста, введи число")
                    return
            elif field_name == "spec":
                car_data[actual_field] = [line.strip() for line in message.text.split("\n") if line.strip()]
            else:
                car_data[actual_field] = message.text.strip()
            
            await state.update_data(car_data=car_data)
            
            card_text = format_car_card(car_data, show_price=False)
            await message.answer(
                "✅ Сохранено!\n\n" + card_text,
                reply_markup=get_edit_card_kb(),
                parse_mode="Markdown"
            )
            await state.set_state(KPStates.editing_card)
            logger.info(f"User {message.from_user.id} edited field {field_name}")
    
    except Exception as e:
        logger.error(f"Error saving field: {e}")
        await message.answer("❌ Ошибка при сохранении. Попробуй ещё раз.")


@dp.callback_query(F.data == "proceed_price")
async def proceed_to_price(callback: types.CallbackQuery, state: FSMContext):
    """Переход к указанию цены"""
    await callback.message.answer(
        "💰 **Шаг 2 из 3:** Укажи цену автомобиля\n\n"
        "Введи цену в рублях (только число):",
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.waiting_price)
    await callback.answer()


@dp.message(KPStates.waiting_price, F.text)
async def process_price(message: types.Message, state: FSMContext):
    """Обработка цены"""
    try:
        price_str = message.text.replace(" ", "").replace(",", "").replace("₽", "")
        price = int(price_str)
        
        if price < 10000 or price > 1000000000:
            await message.answer("⚠️ Цена должна быть от 10,000 до 1,000,000,000 руб")
            return
        
        data = await state.get_data()
        car_data = data.get("car_data", {})
        car_data['price_rub'] = price
        await state.update_data(car_data=car_data)
        
        await message.answer(
            f"✅ Цена: {price:,} руб\n\n".replace(',', ' ') +
            "Выбери тип цены:",
            reply_markup=get_price_note_kb(),
            parse_mode="Markdown"
        )
        await state.set_state(KPStates.waiting_price_note)
        
    except ValueError:
        await message.answer("⚠️ Введи только число (например: 5000000)")


@dp.callback_query(F.data.startswith("price_note_"))
async def process_price_note(callback: types.CallbackQuery, state: FSMContext):
    """Обработка типа цены"""
    price_type = callback.data.replace("price_note_", "")
    
    price_notes = {
        "ндс": "с НДС",
        "безндс": "без НДС",
        "наличные": "наличные"
    }
    
    data = await state.get_data()
    car_data = data.get("car_data", {})
    car_data['price_note'] = price_notes.get(price_type, "с НДС")
    await state.update_data(car_data=car_data)
    
    await callback.message.answer(
        f"✅ Цена: {car_data['price_rub']:,} руб ({car_data['price_note']})".replace(',', ' ')
    )
    
    await callback.message.answer(
        "📸 **Шаг 3 из 3:** Загрузи 3-4 фото автомобиля.\n\n"
        "Фото можно отправить по одному или альбомом.\n"
        "Минимум 3 фото для создания КП.",
        parse_mode="Markdown"
    )
    
    photos_count = len(data.get("photos", []))
    await callback.message.answer(
        f"📊 Загружено фото: {photos_count}/4",
        reply_markup=get_photos_kb(photos_count)
    )
    
    await state.set_state(KPStates.waiting_photos)
    await callback.answer()


@dp.message(KPStates.waiting_photos, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка фото"""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) >= 4:
        await message.answer("⚠️ Максимум 4 фото. Нажми \"Готово\" для создания PDF.")
        return
    
    photo_file_id = message.photo[-1].file_id
    photos.append(photo_file_id)
    await state.update_data(photos=photos)
    
    if len(photos) >= 4:
        status_text = f"✅ Загружено {len(photos)}/4 фото\n\n🎉 Максимум достигнут! Нажми \"Готово\" для создания PDF."
    elif len(photos) >= 3:
        status_text = f"✅ Загружено {len(photos)}/4 фото\n\n🎉 Минимум достигнут! Можешь нажать \"Готово\" или загрузить ещё одно."
    else:
        status_text = f"✅ Загружено {len(photos)}/4 фото\n\nОсталось минимум: {3 - len(photos)}"
    
    await message.answer(
        status_text,
        reply_markup=get_photos_kb(len(photos))
    )
    logger.info(f"User {message.from_user.id} uploaded photo {len(photos)}/4")


@dp.callback_query(F.data == "photos_done")
async def finalize_kp(callback: types.CallbackQuery, state: FSMContext):
    """Создание PDF"""
    data = await state.get_data()
    photos = data.get("photos", [])
    car_data = data.get("car_data", {})
    
    if len(photos) < 3:
        await callback.answer("⚠️ Нужно минимум 3 фото!", show_alert=True)
        return
    
    await callback.message.answer("⏳ Создаю PDF... Подожди немного.")
    
    try:
        # Скачиваем фото
        photo_paths = []
        for i, photo_id in enumerate(photos):
            file = await bot.get_file(photo_id)
            file_path = f"/tmp/photo_{i}.jpg"
            await bot.download_file(file.file_path, file_path)
            photo_paths.append(file_path)
        
        # Генерируем PDF
        from pdf_generator import generate_kp_pdf
        pdf_path = generate_kp_pdf(car_data, photo_paths)
        
        # Отправляем PDF
        pdf_file = types.FSInputFile(pdf_path)
        await callback.message.answer_document(
            pdf_file,
            caption=f"✅ **КП готово!**\n\n📝 {car_data.get('title', 'Автомобиль')}",
            parse_mode="Markdown"
        )
        
        # Логируем в Google Sheets
        username = callback.from_user.full_name or callback.from_user.username or "Unknown"
        sheets_logger.log_kp(
            user_id=callback.from_user.id,
            username=username,
            car_data=car_data,
            photos_count=len(photos)
        )
        
        await callback.message.answer(
            "🎉 Готово! КП создано и записано в базу.",
            reply_markup=get_main_menu()
        )
        
        logger.info(f"User {callback.from_user.id} created KP successfully")
        await state.clear()
        await callback.answer("Готово! ✅")
        
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        await callback.message.answer(
            "❌ Ошибка при создании PDF. Попробуй ещё раз.",
            reply_markup=get_main_menu()
        )
        await state.clear()
        await callback.answer()


@dp.callback_query(F.data == "reset_photos")
async def reset_photos_handler(callback: types.CallbackQuery, state: FSMContext):
    """Сброс фото"""
    await state.update_data(photos=[])
    await callback.message.answer("🔄 Фото сброшены. Загружай заново.")
    await callback.answer()


@dp.callback_query(F.data == "reset_start")
async def reset_start_handler(callback: types.CallbackQuery, state: FSMContext):
    """Начать заново"""
    await state.clear()
    await callback.message.answer(
        "🔄 Начинаем заново. Выбери способ:",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """Отмена"""
    await state.clear()
    await callback.message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )
    await callback.answer()
    logger.info(f"User {callback.from_user.id} cancelled action")


@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: types.Message):
    """Справка"""
    help_text = (
        "📖 **Как создать КП:**\n\n"
        "**📝 Режим \"Текст\":**\n"
        "1. Скопируй описание с Авито (Ctrl+A, Ctrl+C)\n"
        "2. Вставь в бота\n"
        "3. Проверь данные\n"
        "4. Укажи цену\n"
        "5. Загрузи фото\n\n"
        "**📸 Режим \"Скриншот\":**\n"
        "1. Сделай скриншоты характеристик\n"
        "2. Отправь все фото боту\n"
        "3. Проверь данные\n"
        "4. Укажи цену\n"
        "5. Загрузи фото\n\n"
        "✨ **Бот распознает всё автоматически!**"
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message()
async def unknown_message(message: types.Message, state: FSMContext):
    """Обработка неизвестных сообщений"""
    current_state = await state.get_state()
    
    # Если в процессе создания КП - игнорируем
    if current_state:
        return
    
    await message.answer(
        "🤔 Не понимаю эту команду.\n\n"
        "Используй кнопки меню для навигации.",
        reply_markup=get_main_menu()
    )


# ==================== ЗАПУСК ====================

async def on_startup():
    """При запуске бота"""
    logger.info("=" * 50)
    logger.info("Бот запущен!")
    logger.info(f"Whitelist enabled: {bool(ALLOWED_USERS)}")
    if ALLOWED_USERS:
        logger.info(f"Allowed users: {ALLOWED_USERS}")
    logger.info("=" * 50)


async def on_shutdown():
    """При остановке бота"""
    logger.info("Бот остановлен")


async def main():
    """Главная функция"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
