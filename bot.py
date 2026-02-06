#!/usr/bin/env python3
"""
Telegram бот "Генератор КП"
Бесплатный вариант без API
"""

import os
import logging
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
    editing_card = State()
    editing_field = State()
    waiting_photos = State()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Белый список (раскомментируй и добавь user_id для ограничения доступа)
ALLOWED_USERS = []
# Пример:
# ALLOWED_USERS = [123456789, 987654321]

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ==================== КЛАВИАТУРЫ ====================

def get_main_menu():
    """Главное меню"""
    keyboard = [
        [KeyboardButton(text="📝 Создать КП")],
        [KeyboardButton(text="ℹ️ Помощь")],
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
            InlineKeyboardButton(text="💰 Цена", callback_data="edit_price"),
        ],
        [
            InlineKeyboardButton(text="📋 Спецификация", callback_data="edit_spec"),
        ],
        [
            InlineKeyboardButton(text="✅ Всё верно → Загрузить фото", callback_data="proceed_photos"),
        ],
        [
            InlineKeyboardButton(text="🔄 Вставить описание заново", callback_data="reset_description"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
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

def format_car_card(data: dict) -> str:
    """Форматирует карточку автомобиля"""
    lines = ["📋 **Карточка автомобиля:**\n"]
    
    lines.append(f"📝 **Название:** {data.get('title') or '❓ Не указано'}")
    lines.append(f"📅 **Год:** {data.get('year') or '❓ Не указан'}")
    lines.append(f"🚗 **Привод:** {data.get('drive') or '❓ Не указан'}")
    lines.append(f"⚙️ **Двигатель:** {data.get('engine_short') or '❓ Не указан'}")
    lines.append(f"🔧 **Коробка:** {data.get('gearbox') or '❓ Не указана'}")
    lines.append(f"🎨 **Цвет:** {data.get('color') or '❓ Нужно указать'}")
    
    mileage = data.get('mileage_km')
    if mileage:
        lines.append(f"📊 **Пробег:** {mileage:,} км".replace(',', ' '))
    else:
        lines.append(f"📊 **Пробег:** ❓ Нужно указать")
    
    price = data.get('price_rub')
    if price:
        lines.append(f"💰 **Цена:** {price:,} руб".replace(',', ' '))
    else:
        lines.append(f"💰 **Цена:** ❓ Нужно указать")
    
    lines.append(f"📝 **Примечание к цене:** {data.get('price_note', 'с НДС')}")
    
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


# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    user_id = message.from_user.id
    
    # Проверка whitelist
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await message.answer("⛔️ У вас нет доступа к этому боту.")
        logger.warning(f"Unauthorized access attempt from user {user_id}")
        return
    
    await state.clear()
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу создать коммерческое предложение (КП) для автомобиля.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )
    logger.info(f"User {user_id} started bot")


@dp.message(F.text == "📝 Создать КП")
async def start_create_kp(message: types.Message, state: FSMContext):
    """Начало создания КП"""
    await state.clear()
    
    await message.answer(
        "📋 Отлично! Давай создадим КП.\n\n"
        "**Шаг 1 из 2:** Отправь мне описание автомобиля.\n\n"
        "Можешь вставить полное описание (спецификацию) из Авито или другого сайта — "
        "я автоматически извлеку все нужные данные.\n\n"
        "После этого ты сможешь проверить и отредактировать каждое поле.",
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.waiting_description)
    logger.info(f"User {message.from_user.id} started creating KP")


@dp.message(KPStates.waiting_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания"""
    try:
        # Парсим описание
        parser = CarDescriptionParser()
        description_text = message.text
        parsed_data = parser.parse(description_text)
        
        # Сохраняем в состояние
        await state.update_data(
            description_text=description_text,
            car_data=parsed_data,
            photos=[]
        )
        
        # Формируем карточку
        card_text = format_car_card(parsed_data)
        
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


@dp.callback_query(F.data.startswith("edit_"))
async def handle_edit_field(callback: types.CallbackQuery, state: FSMContext):
    """Обработка редактирования полей"""
    field_name = callback.data.replace("edit_", "")
    
    prompts = {
        "title": "Введи название автомобиля:",
        "year": "Введи год выпуска (например: 2024):",
        "drive": "Введи привод (Полный/Передний/Задний):",
        "engine": "Введи описание двигателя (например: 258 л.с., 2.0, Бензин):",
        "gearbox": "Введи коробку передач (Автомат/Механика/Робот/Вариатор):",
        "color": "Введи цвет автомобиля:",
        "mileage": "Введи пробег в км (только число):",
        "price": "Введи цену в рублях (только число):",
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
            "price": "price_rub",
            "spec": "spec_items",
        }
        
        actual_field = field_mapping.get(field_name)
        
        if actual_field:
            # Числовые поля
            if field_name in ["year", "mileage", "price"]:
                try:
                    value = int(message.text.replace(" ", "").replace(",", ""))
                    car_data[actual_field] = value
                except ValueError:
                    await message.answer("⚠️ Пожалуйста, введи число")
                    return
            # Спецификация
            elif field_name == "spec":
                car_data[actual_field] = [line.strip() for line in message.text.split("\n") if line.strip()]
            # Текстовые поля
            else:
                car_data[actual_field] = message.text.strip()
            
            await state.update_data(car_data=car_data)
            
            # Показываем обновлённую карточку
            card_text = format_car_card(car_data)
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


@dp.callback_query(F.data == "proceed_photos")
async def proceed_to_photos(callback: types.CallbackQuery, state: FSMContext):
    """Переход к загрузке фото"""
    await callback.message.answer(
        "📸 **Шаг 2 из 2:** Загрузи 3-4 фото автомобиля.\n\n"
        "Фото можно отправить по одному или альбомом.\n"
        "Минимум 3 фото для создания КП.",
        parse_mode="Markdown"
    )
    
    data = await state.get_data()
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
    
    # Сохраняем file_id
    photo_file_id = message.photo[-1].file_id
    photos.append(photo_file_id)
    await state.update_data(photos=photos)
    
    status_text = f"✅ Загружено фото: {len(photos)}/4"
    
    if len(photos) >= 3:
        status_text += "\n\n🎉 Минимум достигнут! Можешь нажать \"Готово\" или загрузить ещё."
    else:
        status_text += f"\n\nОсталось минимум: {3 - len(photos)}"
    
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
        # Логируем в Google Sheets
        username = callback.from_user.full_name or callback.from_user.username or "Unknown"
        sheets_logger.log_kp(
            user_id=callback.from_user.id,
            username=username,
            car_data=car_data,
            photos_count=len(photos)
        )
        
        # TODO: Здесь будет генерация PDF
        
        kp_info = (
            f"✅ **КП готово!**\n\n"
            f"📝 {car_data.get('title', 'Автомобиль')}\n"
            f"📅 {car_data.get('year', '—')}\n"
            f"💰 {car_data.get('price_rub', '—'):,} руб\n\n".replace(',', ' ')
        )
        kp_info += "📄 PDF будет готов на следующем этапе разработки\n"
        kp_info += "📊 Данные записаны в Google Sheets"
        
        await callback.message.answer(
            kp_info,
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        
        logger.info(f"User {callback.from_user.id} created KP successfully")
        await state.clear()
        await callback.answer("Готово! ✅")
        
    except Exception as e:
        logger.error(f"Error creating KP: {e}")
        await callback.message.answer(
            "❌ Ошибка при создании КП. Попробуй ещё раз.",
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


@dp.callback_query(F.data == "reset_description")
async def reset_description_handler(callback: types.CallbackQuery, state: FSMContext):
    """Повторный ввод описания"""
    await callback.message.answer("🔄 Вставь описание заново:")
    await state.set_state(KPStates.waiting_description)
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
        "1️⃣ Нажми **\"Создать КП\"**\n"
        "2️⃣ Вставь описание автомобиля (спецификацию)\n"
        "3️⃣ Проверь и отредактируй данные\n"
        "4️⃣ Загрузи 3-4 фото\n"
        "5️⃣ Получи готовый PDF\n\n"
        "✨ **Бот автоматически распознает:**\n"
        "• Модель и год\n"
        "• Двигатель и мощность\n"
        "• Привод и коробку\n"
        "• Технические характеристики\n\n"
        "❓ Если бот не распознал какие-то данные, "
        "ты всегда можешь отредактировать любое поле вручную."
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message()
async def unknown_message(message: types.Message):
    """Обработка неизвестных сообщений"""
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
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
