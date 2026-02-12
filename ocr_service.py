#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR сервис на локальном Tesseract.
УЛУЧШЕННАЯ ВЕРСИЯ для мобильных скриншотов Авито
"""

from __future__ import annotations

import re
from typing import Optional

import pytesseract
from PIL import Image, ImageOps, ImageEnhance

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False


# Список мусора который нужно удалить из OCR результата
GARBAGE_PATTERNS = [
    # Кнопки и действия
    r'позвонить',
    r'написать',
    r'поделиться',
    r'избранное',
    r'пожаловаться',
    r'в\s+избранное',
    r'добавить\s+в',
    
    # Навигация
    r'назад',
    r'меню',
    r'главная',
    r'каталог',
    r'поиск',
    r'фильтры',
    
    # Авито UI
    r'авито',
    r'доставка\s+авито',
    r'безопасная\s+сделка',
    r'защита\s+покупателя',
    r'гарантия\s+авито',
    r'только\s+на\s+авито',
    
    # Контакты
    r'\+7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}',  # Телефоны
    r'\d{3}[\s\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}',  # Телефоны без +7
    r'показать\s+телефон',
    r'показать\s+номер',
    
    # Адреса (упрощённо)
    r'москва,\s*ул\.',
    r'санкт-петербург,\s*ул\.',
    r'\d+-я\s+ямская',
    r'показать\s+на\s+карте',
    
    # Реклама
    r'реклама',
    r'реклама\s+на\s+сайте',
    r'купить',
    r'заказать',
    r'оформить',
    r'кредит\s+от',
    r'рассрочка',
    r'в\s+кредит\s+от',
    r'лизинг',
    
    # Оценки и отзывы
    r'\d+,\d+\s+★',
    r'\d+\s+отзыв',
    r'рейтинг',
    r'отвечает\s+на\s+сообщения',
    
    # Разное
    r'посмотреть\s+предложения',
    r'другие\s+объявления',
    r'похожие\s+объявления',
    r'сохранить',
    r'поделиться',
]


def _crop_borders(img: Image.Image) -> Image.Image:
    """
    Обрезает верх и низ скриншота (где обычно кнопки/меню)
    """
    width, height = img.size
    
    # Обрезаем верх (10%) и низ (15%)
    crop_top = int(height * 0.10)
    crop_bottom = int(height * 0.85)
    
    return img.crop((0, crop_top, width, crop_bottom))


def _preprocess_pil(img: Image.Image) -> Image.Image:
    """
    Базовая предобработка (без OpenCV)
    """
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Обрезаем кнопки
    img = _crop_borders(img)
    
    # Серый
    img = ImageOps.grayscale(img)
    
    # Увеличение x3 (было x2)
    scale = 3
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    
    # Контраст + резкость
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    
    # Threshold
    img = img.point(lambda x: 0 if x < 140 else 255, mode="1")
    
    return img


def _preprocess_opencv(img: Image.Image) -> Image.Image:
    """
    Улучшенная предобработка (OpenCV)
    """
    if not OPENCV_AVAILABLE:
        return _preprocess_pil(img)
    
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Обрезаем кнопки
    img = _crop_borders(img)
    
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    
    # Увеличение x3
    gray = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    
    # Денойзинг
    gray = cv2.fastNlMeansDenoising(gray, None, h=10)
    
    # Адаптивный threshold
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
    )
    
    # Морфология (убрать мелкие артефакты)
    kernel = np.ones((2, 2), np.uint8)
    thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel)
    
    return Image.fromarray(thr)


def _clean_text(text: str) -> str:
    """
    Постобработка: убираем мусор из OCR результата
    """
    text_lower = text.lower()
    
    # Удаляем мусор по паттернам
    for pattern in GARBAGE_PATTERNS:
        text_lower = re.sub(pattern, '', text_lower, flags=re.IGNORECASE)
    
    # Восстанавливаем из нижнего регистра (нужны заглавные)
    # Простой способ: берём оригинал, но маскируем мусор пробелами
    cleaned_lines = []
    for line in text.split('\n'):
        line_lower = line.lower()
        
        # Проверяем есть ли мусор в строке
        is_garbage = False
        for pattern in GARBAGE_PATTERNS:
            if re.search(pattern, line_lower, re.IGNORECASE):
                is_garbage = True
                break
        
        if not is_garbage and line.strip():
            cleaned_lines.append(line.strip())
    
    text = '\n'.join(cleaned_lines)
    
    # Нормализация пробелов
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Убираем строки из 1-2 символов (обычно мусор)
    lines = text.split('\n')
    lines = [line for line in lines if len(line) > 2]
    
    return '\n'.join(lines).strip()


def ocr_image_to_text(image_path: str) -> str:
    """
    Главная функция OCR: принимает путь к картинке, возвращает распознанный текст.
    УЛУЧШЕННАЯ ВЕРСИЯ для Авито скриншотов.
    """
    img = Image.open(image_path)
    
    # Предобработка (OpenCV если есть, иначе PIL)
    if OPENCV_AVAILABLE:
        img_prep = _preprocess_opencv(img)
    else:
        img_prep = _preprocess_pil(img)
    
    # Tesseract конфиг (оптимизированный для таблиц/характеристик)
    # PSM 6 = единый блок текста (хорошо для характеристик)
    # OEM 3 = лучший движок
    config = "--oem 3 --psm 6 -c tessedit_char_whitelist=АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюяABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:-/()№ "
    
    # Распознаём
    text = pytesseract.image_to_string(img_prep, lang="rus+eng", config=config)
    
    # Постобработка - чистим мусор
    text = _clean_text(text)
    
    return text
