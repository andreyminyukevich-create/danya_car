#!/usr/bin/env python3
"""
Telegram бот "Генератор КП"
Бесплатный вариант без API
"""

import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния FSM
class KPStates(StatesGroup):
    waiting_description = State()
    editing_card = State()
    editing_field = State()
    waiting_photos = State()

# Токен бота (будет из переменных окружения)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Белый список пользователей (опционально)
ALLOWED_USERS = [
    # Добавь сюда telegram user_id сотрудников
    # 123456789,
    # 987654321,
]

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ==================== КЛАВИАТУРЫ ====================

def get_main_menu():
    """Главное меню"""
    kb = [
        [KeyboardButton(text="📝 Создать КП")],
        [KeyboardButton(text="📋 Мои черновики")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_edit_card_kb():
    """Кнопки для редактирования карточки"""
    kb = [
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
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_photos_kb():
    """Кнопки для загрузки фото"""
    kb = [
        [InlineKeyboardButton(text="✅ Готово (фото загружены)", callback_data="photos_done")],
        [InlineKeyboardButton(text="🔄 Сбросить фото", callback_data="reset_photos")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start"""
    user_id = message.from_user.id
    
    # Проверка whitelist (опционально)
    # if ALLOWED_USERS and user_id not in ALLOWED_USERS:
    #     await message.answer("⛔️ У вас нет доступа к этому боту.")
    #     return
    
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я помогу тебе создать коммерческое предложение (КП) для автомобиля.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu()
    )


@dp.message(F.text == "📝 Создать КП")
async def start_create_kp(message: types.Message, state: FSMContext):
    """Начало создания КП"""
    await message.answer(
        "📋 Отлично! Давай создадим КП.\n\n"
        "**Шаг 1 из 2:** Отправь мне описание автомобиля.\n\n"
        "Можешь вставить полное описание (спецификацию) из Авито или другого сайта - "
        "я автоматически извлеку все нужные данные.\n\n"
        "После этого ты сможешь проверить и отредактировать каждое поле.",
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.waiting_description)


@dp.message(KPStates.waiting_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания автомобиля"""
    # Импортируем парсер
    from parser import CarDescriptionParser
    
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
    
    # Формируем карточку для показа
    card_text = format_car_card(parsed_data)
    
    await message.answer(
        "✅ Описание обработано!\n\n" + card_text,
        reply_markup=get_edit_card_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.editing_card)


def format_car_card(data: dict) -> str:
    """Форматирует карточку автомобиля для показа"""
    lines = ["📋 **Карточка автомобиля:**\n"]
    
    lines.append(f"📝 **Название:** {data.get('title') or '❓ Не указано'}")
    lines.append(f"📅 **Год:** {data.get('year') or '❓ Не указан'}")
    lines.append(f"🚗 **Привод:** {data.get('drive') or '❓ Не указан'}")
    lines.append(f"⚙️ **Двигатель:** {data.get('engine_short') or '❓ Не указан'}")
    lines.append(f"🔧 **Коробка:** {data.get('gearbox') or '❓ Не указана'}")
    lines.append(f"🎨 **Цвет:** {data.get('color') or '❓ Нужно указать'}")
    lines.append(f"📊 **Пробег:** {data.get('mileage_km') or '❓ Нужно указать'} км")
    lines.append(f"💰 **Цена:** {data.get('price_rub') or '❓ Нужно указать'} руб")
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


@dp.callback_query(F.data.startswith("edit_"))
async def handle_edit_field(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопок редактирования полей"""
    field_name = callback.data.replace("edit_", "")
    
    field_prompts = {
        "title": "Введите название автомобиля:",
        "year": "Введите год выпуска (например: 2024):",
        "drive": "Введите привод (Полный/Передний/Задний):",
        "engine": "Введите описание двигателя (например: 258 л.с., 2.0, Бензин):",
        "gearbox": "Введите коробку передач (Автомат/Механика/Робот/Вариатор):",
        "color": "Введите цвет автомобиля:",
        "mileage": "Введите пробег в км (только число):",
        "price": "Введите цену в рублях (только число):",
        "spec": "Отправьте список пунктов спецификации (каждый пункт с новой строки):",
    }
    
    await callback.message.answer(field_prompts.get(field_name, "Введите значение:"))
    await state.update_data(editing_field=field_name)
    await state.set_state(KPStates.editing_field)
    await callback.answer()


@dp.message(KPStates.editing_field, F.text)
async def save_edited_field(message: types.Message, state: FSMContext):
    """Сохранение отредактированного поля"""
    data = await state.get_data()
    field_name = data.get("editing_field")
    car_data = data.get("car_data", {})
    
    # Маппинг полей
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
        # Обработка числовых полей
        if field_name in ["year", "mileage", "price"]:
            try:
                value = int(message.text.replace(" ", "").replace(",", ""))
                car_data[actual_field] = value
            except ValueError:
                await message.answer("⚠️ Пожалуйста, введите число")
                return
        elif field_name == "spec":
            # Спецификация - список строк
            car_data[actual_field] = [line.strip() for line in message.text.split("\n") if line.strip()]
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


@dp.callback_query(F.data == "proceed_photos")
async def proceed_to_photos(callback: types.CallbackQuery, state: FSMContext):
    """Переход к загрузке фото"""
    await callback.message.answer(
        "📸 **Шаг 2 из 2:** Загрузи 3-4 фото автомобиля.\n\n"
        "Фото можно отправить по одному или альбомом.\n"
        "После загрузки всех фото нажми кнопку **\"Готово\"**.",
        reply_markup=get_photos_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.waiting_photos)
    await callback.answer()


@dp.message(KPStates.waiting_photos, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Обработка загруженных фото"""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    # Сохраняем file_id фото
    photo_file_id = message.photo[-1].file_id
    photos.append(photo_file_id)
    
    await state.update_data(photos=photos)
    
    if len(photos) >= 4:
        await message.answer(
            f"✅ Загружено {len(photos)} фото (максимум 4).\n"
            "Нажми **\"Готово\"** для создания PDF.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"✅ Загружено {len(photos)} фото.\n"
            f"Осталось минимум {max(0, 3 - len(photos))} фото.",
            parse_mode="Markdown"
        )


@dp.callback_query(F.data == "photos_done")
async def finalize_kp(callback: types.CallbackQuery, state: FSMContext):
    """Финализация и создание PDF"""
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if len(photos) < 3:
        await callback.answer("⚠️ Нужно минимум 3 фото!", show_alert=True)
        return
    
    await callback.message.answer(
        "⏳ Создаю PDF... Подожди немного.",
        parse_mode="Markdown"
    )
    
    # Здесь будет генерация PDF
    # TODO: Реализовать генерацию PDF
    
    await callback.message.answer(
        "✅ **КП готово!**\n\n"
        "📄 [Пока заглушка - PDF будет на следующем шаге]",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    
    await state.clear()
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    await callback.message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "reset_photos")
async def reset_photos_handler(callback: types.CallbackQuery, state: FSMContext):
    """Сброс загруженных фото"""
    await state.update_data(photos=[])
    await callback.message.answer("🔄 Фото сброшены. Загружай заново.")
    await callback.answer()


@dp.callback_query(F.data == "reset_description")
async def reset_description_handler(callback: types.CallbackQuery, state: FSMContext):
    """Повторный ввод описания"""
    await callback.message.answer(
        "🔄 Вставь описание заново:",
        reply_markup=get_main_menu()
    )
    await state.set_state(KPStates.waiting_description)
    await callback.answer()


@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: types.Message):
    """Справка"""
    await message.answer(
        "📖 **Как создать КП:**\n\n"
        "1️⃣ Нажми **\"Создать КП\"**\n"
        "2️⃣ Вставь описание автомобиля (спецификацию)\n"
        "3️⃣ Проверь и отредактируй данные\n"
        "4️⃣ Загрузи 3-4 фото\n"
        "5️⃣ Получи готовый PDF\n\n"
        "✨ Бот автоматически распознает:\n"
        "• Модель и год\n"
        "• Двигатель и мощность\n"
        "• Привод и коробку\n"
        "• Технические характеристики",
        parse_mode="Markdown"
    )


@dp.message(F.text == "📋 Мои черновики")
async def drafts_command(message: types.Message):
    """Черновики (пока заглушка)"""
    await message.answer(
        "📋 Черновики пока не реализованы.\n"
        "Будет в следующей версии!",
        parse_mode="Markdown"
    )


# ==================== ЗАПУСК ====================

async def main():
    """Запуск бота"""
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
