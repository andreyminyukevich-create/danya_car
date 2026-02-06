#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот "Генератор КП"
Полная версия с правильным flow + защита от длинных копипастов Авито.
+ команда /ocr_test (проверка локального OCR через Tesseract)
"""

import os
import time
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from parser import CarDescriptionParser
from sheets_logger import sheets_logger
from ocr_service import ocr_image_to_text  # <-- новый модуль OCR


# ==================== НАСТРОЙКИ ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Белый список (если пусто — доступ всем)
ALLOWED_USERS = []


# ===== Ограничения Telegram / Авито =====
TG_MSG_LIMIT = 4096
SAFE_OUTPUT_LIMIT = 3500        # чтобы ответ точно НЕ дробился (Markdown кушает символы)
SAFE_INPUT_LIMIT = 12000        # сколько максимум держим для парсера
PART_WINDOW_SEC = 25            # окно для ожидания второй части
FIRST_PART_NEAR_LIMIT = 3800    # если первая часть >= этого — скорее всего телега порезала и будет 2-я часть


# ==================== FSM ====================

class KPStates(StatesGroup):
    waiting_description = State()
    editing_card = State()
    editing_field = State()
    waiting_price = State()
    waiting_price_note = State()
    waiting_photos = State()


# ==================== INIT ====================

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ==================== UI ====================

def get_main_menu():
    keyboard = [
        [KeyboardButton(text="📝 Создать КП")],
        [KeyboardButton(text="📖 Инструкция"), KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_edit_card_kb():
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
            InlineKeyboardButton(text="🔄 Вставить описание заново", callback_data="reset_description"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_price_note_kb():
    keyboard = [
        [InlineKeyboardButton(text="💼 С НДС", callback_data="price_note_ндс")],
        [InlineKeyboardButton(text="💵 Без НДС", callback_data="price_note_безндс")],
        [InlineKeyboardButton(text="💰 Наличные", callback_data="price_note_наличные")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_photos_kb(photos_count: int):
    keyboard = []
    if photos_count >= 3:
        keyboard.append([InlineKeyboardButton(text="✅ Готово (создать PDF)", callback_data="photos_done")])

    keyboard.extend([
        [InlineKeyboardButton(text="🔄 Сбросить фото", callback_data="reset_photos")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==================== HELPERS ====================

def clamp_text(text: str, limit: int) -> str:
    """Обрезает текст до limit символов (с конца), добавляя пометку."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n…(обрезано, чтобы поместиться в одно сообщение)"


def normalize_space(text: str) -> str:
    if not text:
        return ""
    return "\n".join([line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")])


def now_ts() -> float:
    return time.time()


def should_wait_second_part(first_part: str) -> bool:
    """
    Эвристика:
    Если первая часть близка к лимиту телеги — часто это обрезанный копипаст,
    значит ждём вторую часть / "готово".
    """
    if not first_part:
        return False
    return len(first_part) >= FIRST_PART_NEAR_LIMIT


def format_car_card(data: dict, show_price: bool = False) -> str:
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
            lines.append("📊 **Пробег:** Новый автомобиль")
        else:
            lines.append(f"📊 **Пробег:** {mileage:,} км".replace(',', ' '))
    else:
        lines.append("📊 **Пробег:** ❓ Нужно указать")

    if show_price:
        price = data.get('price_rub')
        if price:
            lines.append(f"💰 **Цена:** {price:,} руб".replace(',', ' '))
            lines.append(f"📝 **Примечание:** {data.get('price_note', 'с НДС')}")
        else:
            lines.append("💰 **Цена:** ❓ Будет указана на следующем шаге")

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


async def parse_and_show_card(message: types.Message, state: FSMContext, description_text: str):
    """Парсит текст, сохраняет state и показывает карточку."""
    description_text = normalize_space(description_text).strip()
    description_text = description_text[:SAFE_INPUT_LIMIT]

    parser = CarDescriptionParser()
    parsed_data = parser.parse(description_text)

    await state.update_data(
        description_text=description_text,
        car_data=parsed_data,
        photos=[],
        # чистим буфер копипаста
        desc_first_part="",
        desc_joined="",
        desc_started_at=0.0,
        desc_waiting_second=False,
        # выключаем OCR тест, если он был включён
        _ocr_test_mode=False,
    )

    card_text = format_car_card(parsed_data, show_price=False)
    card_text = clamp_text(card_text, SAFE_OUTPUT_LIMIT)

    await message.answer(
        "✅ Описание обработано!\n\n" + card_text,
        reply_markup=get_edit_card_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.editing_card)
    logger.info(f"User {message.from_user.id} parsed description successfully")


def cut_to_one_message(text: str, limit: int = SAFE_OUTPUT_LIMIT) -> str:
    """Обрезает текст, чтобы точно влезло в одно сообщение."""
    return clamp_text(text or "", limit)


# ==================== HANDLERS ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

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


# ---------- OCR TEST ----------
@dp.message(Command("ocr_test"))
async def cmd_ocr_test(message: types.Message, state: FSMContext):
    """
    Тест OCR:
    1) /ocr_test
    2) пользователь кидает 1 скрин таблицы "Характеристики"
    3) бот возвращает распознанный текст (обрезанный)
    """
    await state.update_data(_ocr_test_mode=True)
    await message.answer(
        "Ок! Отправь 1 скрин блока **«Характеристики»** (таблица).\n"
        "Я распознаю текст и пришлю результат.\n\n"
        "Чтобы выйти из теста — отправь любую команду или начни создание КП.",
        parse_mode="Markdown"
    )


# Хендлер фото для OCR-теста. Важно: общий, но с условием по state.
@dp.message(F.photo)
async def handle_any_photo_for_ocr_test(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("_ocr_test_mode"):
        return  # это не OCR тест — пусть фото ловят другие хендлеры (например waiting_photos)

    try:
        file = await bot.get_file(message.photo[-1].file_id)
        tmp_path = "/tmp/ocr_test.jpg"
        await bot.download_file(file.file_path, tmp_path)

        text = ocr_image_to_text(tmp_path)
        text = cut_to_one_message(text, SAFE_OUTPUT_LIMIT)

        await message.answer("✅ OCR результат:\n\n" + (text or "⚠️ Ничего не распознано"))
    except Exception as e:
        await message.answer(f"❌ Ошибка OCR: {e}")


@dp.message(F.text == "📝 Создать КП")
async def start_create_kp(message: types.Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "📋 Отлично! Давай создадим КП.\n\n"
        "**Шаг 1 из 3:** Отправь мне описание автомобиля.\n\n"
        "💡 **Как скопировать с Авито:**\n"
        "1. Открой объявление на Авито\n"
        "2. Выдели всю страницу (Ctrl+A или Cmd+A)\n"
        "3. Скопируй (Ctrl+C или Cmd+C)\n"
        "4. Вставь сюда (Ctrl+V или Cmd+V)\n\n"
        "Бот автоматически найдёт все нужные данные! ✨\n\n"
        "Если Telegram разобьёт копипаст на 2 сообщения — просто отправь вторую часть следом.\n"
        "Если хочешь завершить — напиши **готово**.",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await state.update_data(
        desc_first_part="",
        desc_joined="",
        desc_started_at=0.0,
        desc_waiting_second=False,
        _ocr_test_mode=False,
    )
    await state.set_state(KPStates.waiting_description)
    logger.info(f"User {message.from_user.id} started creating KP")


@dp.message(F.text == "📖 Инструкция")
async def show_instruction(message: types.Message):
    instruction = """📖 **ИНСТРУКЦИЯ: Как скопировать объявление с Авито**

**Способ 1: Копировать всю страницу (рекомендуется)**

1️⃣ Открой объявление на Авито в браузере  
2️⃣ Нажми **Ctrl+A** (Windows) или **Cmd+A** (Mac)  
3️⃣ Нажми **Ctrl+C** (Windows) или **Cmd+C** (Mac)  
4️⃣ Вернись в бота и нажми **Ctrl+V** (Windows) или **Cmd+V** (Mac)

✅ **Бот автоматически найдёт:**  
- Название, год, характеристики  
- Цвет, пробег, спецификацию  

⚠️ Если Telegram разобьёт вставку на 2 сообщения — просто отправь вторую часть следом.  
Чтобы завершить ввод — напиши **готово**.
"""
    await message.answer(instruction, parse_mode="Markdown")


# ---- ВАЖНО: хендлер "готово" должен быть ВЫШЕ общего хендлера waiting_description ----
@dp.message(KPStates.waiting_description, lambda m: (m.text or "").strip().lower() == "готово")
async def process_description_finalize(message: types.Message, state: FSMContext):
    """Финализация: парсим уже собранный текст (если он есть)."""
    try:
        data = await state.get_data()
        joined = (data.get("desc_joined") or "").strip()
        first = (data.get("desc_first_part") or "").strip()

        description_text = (joined or first or "").strip()
        if not description_text:
            await message.answer("⚠️ Я не вижу текста. Вставь описание с Авито ещё раз.")
            return

        await parse_and_show_card(message, state, description_text)

    except Exception as e:
        logger.error(f"Error parsing description finalize: {e}")
        await message.answer("❌ Ошибка при обработке описания. Попробуй ещё раз.")
        await state.clear()


@dp.message(KPStates.waiting_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """
    Приём копипаста:
    - Если текст короткий/обычный → парсим сразу
    - Если текст упёрся в лимит и похоже на разбиение → ждём вторую часть (или "готово")
    - Вторую часть склеиваем, но общий текст режем до SAFE_INPUT_LIMIT
    """
    try:
        txt = normalize_space(message.text or "").strip()

        data = await state.get_data()
        started_at = float(data.get("desc_started_at") or 0.0)
        waiting_second = bool(data.get("desc_waiting_second") or False)
        first_part = (data.get("desc_first_part") or "").strip()
        joined = (data.get("desc_joined") or "").strip()

        # Если это первый кусок
        if not first_part and not joined and not waiting_second:
            first_part = txt
            started_at = now_ts()

            # Если первая часть почти лимитная — ждём вторую
            if should_wait_second_part(first_part):
                await state.update_data(
                    desc_first_part=first_part,
                    desc_joined=first_part,
                    desc_started_at=started_at,
                    desc_waiting_second=True
                )
                await message.answer(
                    "Принял первую часть (она большая и похожа на обрезанную).\n"
                    "Если есть продолжение — отправь вторую часть.\n"
                    "Если продолжения нет — напиши **готово**.",
                    parse_mode="Markdown"
                )
                return

            # Обычный кейс — парсим сразу
            await parse_and_show_card(message, state, first_part)
            return

        # Если ждём вторую часть
        if waiting_second:
            # Если прошло слишком много — считаем, что продолжения нет, парсим то что есть
            if started_at and (now_ts() - started_at) > PART_WINDOW_SEC:
                await parse_and_show_card(message, state, joined or first_part)
                return

            # Склеиваем вторую часть
            combined = (joined + "\n" + txt).strip()
            combined = combined[:SAFE_INPUT_LIMIT]

            await state.update_data(
                desc_joined=combined,
                desc_waiting_second=False,  # после 2-й части сразу парсим (обычно дальше уже мусор)
            )

            await parse_and_show_card(message, state, combined)
            return

        # Если не ждём вторую, но вдруг пришёл ещё кусок (обычно мусор) — игнорим
        await message.answer("Я уже обработал описание. Проверь карточку и при необходимости отредактируй поля кнопками ниже.")

    except Exception as e:
        logger.error(f"Error parsing description: {e}")
        await message.answer("❌ Ошибка при обработке описания. Попробуй ещё раз.", reply_markup=get_main_menu())
        await state.clear()


@dp.callback_query(F.data.startswith("edit_"))
async def handle_edit_field(callback: types.CallbackQuery, state: FSMContext):
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
            card_text = clamp_text(card_text, SAFE_OUTPUT_LIMIT)

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
    await callback.message.answer(
        "💰 **Шаг 2 из 3:** Укажи цену автомобиля\n\n"
        "Введи цену в рублях (только число):",
        parse_mode="Markdown"
    )
    await state.set_state(KPStates.waiting_price)
    await callback.answer()


@dp.message(KPStates.waiting_price, F.text)
async def process_price(message: types.Message, state: FSMContext):
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
            (f"✅ Цена: {price:,} руб\n\n".replace(',', ' ') + "Выбери тип цены:"),
            reply_markup=get_price_note_kb(),
            parse_mode="Markdown"
        )
        await state.set_state(KPStates.waiting_price_note)

    except ValueError:
        await message.answer("⚠️ Введи только число (например: 5000000)")


@dp.callback_query(F.data.startswith("price_note_"))
async def process_price_note(callback: types.CallbackQuery, state: FSMContext):
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

    await message.answer(status_text, reply_markup=get_photos_kb(len(photos)))
    logger.info(f"User {message.from_user.id} uploaded photo {len(photos)}/4")


@dp.callback_query(F.data == "photos_done")
async def finalize_kp(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    car_data = data.get("car_data", {})

    # Имя пользователя (только имя)
    user_name = (callback.from_user.first_name or "").strip()
    if not user_name:
        user_name = (callback.from_user.username or "Менеджер").strip()
    car_data["user_name"] = user_name
    await state.update_data(car_data=car_data)

    if len(photos) < 3:
        await callback.answer("⚠️ Нужно минимум 3 фото!", show_alert=True)
        return

    await callback.message.answer("⏳ Создаю PDF... Подожди немного.")

    try:
        photo_paths = []
        for i, photo_id in enumerate(photos):
            file = await bot.get_file(photo_id)
            file_path = f"/tmp/photo_{i}.jpg"
            await bot.download_file(file.file_path, file_path)
            photo_paths.append(file_path)

        from pdf_generator import generate_kp_pdf
        pdf_path = generate_kp_pdf(car_data, photo_paths)

        pdf_file = types.FSInputFile(pdf_path)
        await callback.message.answer_document(
            pdf_file,
            caption=f"✅ **КП готово!**\n\n📝 {car_data.get('title', 'Автомобиль')}",
            parse_mode="Markdown"
        )

        username = callback.from_user.full_name or callback.from_user.username or "Unknown"
        sheets_logger.log_kp(
            user_id=callback.from_user.id,
            username=username,
            car_data=car_data,
            photos_count=len(photos)
        )

        await callback.message.answer("🎉 Готово! КП создано и записано в базу.", reply_markup=get_main_menu())

        logger.info(f"User {callback.from_user.id} created KP successfully")
        await state.clear()
        await callback.answer("Готово! ✅")

    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        await callback.message.answer("❌ Ошибка при создании PDF. Попробуй ещё раз.", reply_markup=get_main_menu())
        await state.clear()
        await callback.answer()


@dp.callback_query(F.data == "reset_photos")
async def reset_photos_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photos=[])
    await callback.message.answer("🔄 Фото сброшены. Загружай заново.")
    await callback.answer()


@dp.callback_query(F.data == "reset_description")
async def reset_description_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(
        desc_first_part="",
        desc_joined="",
        desc_started_at=0.0,
        desc_waiting_second=False,
        _ocr_test_mode=False,
    )
    await callback.message.answer("🔄 Вставь описание заново:")
    await state.set_state(KPStates.waiting_description)
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Действие отменено.", reply_markup=get_main_menu())
    await callback.answer()
    logger.info(f"User {callback.from_user.id} cancelled action")


@dp.message(F.text == "ℹ️ Помощь")
async def help_command(message: types.Message):
    help_text = (
        "📖 **Как создать КП:**\n\n"
        "1️⃣ Нажми **\"Создать КП\"**\n"
        "2️⃣ Вставь описание автомобиля (всю страницу с Авито!)\n"
        "3️⃣ Проверь и отредактируй данные\n"
        "4️⃣ Укажи цену\n"
        "5️⃣ Загрузи 3-4 фото\n"
        "6️⃣ Получи готовый PDF\n\n"
        "💡 Если Telegram разобьёт вставку на 2 сообщения — пришли вторую часть.\n"
        "Чтобы завершить ввод — напиши **готово**.\n\n"
        "🧪 Для проверки OCR: команда /ocr_test"
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message()
async def unknown_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return
    await message.answer(
        "🤔 Не понимаю эту команду.\n\n"
        "Используй кнопки меню для навигации.",
        reply_markup=get_main_menu()
    )


# ==================== STARTUP / SHUTDOWN ====================

async def on_startup():
    logger.info("=" * 50)
    logger.info("Бот запущен!")
    logger.info(f"Whitelist enabled: {bool(ALLOWED_USERS)}")
    if ALLOWED_USERS:
        logger.info(f"Allowed users: {ALLOWED_USERS}")
    logger.info("=" * 50)


async def on_shutdown():
    logger.info("Бот остановлен")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
