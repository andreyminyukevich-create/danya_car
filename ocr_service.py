#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR сервис на Tesseract.
Быстрый и стабильный для Railway.
"""

from __future__ import annotations

import re
import os
from typing import Optional

from PIL import Image, ImageOps, ImageEnhance

# Tesseract
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("❌ Tesseract not available")

# OpenCV (опционально)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False


# Список мусора для постобработки
GARBAGE_PATTERNS = [
    r'позвонить', r'написать', r'поделиться', r'избранное',
    r'пожаловаться', r'в\s+избранное', r'добавить\s+в',
    r'назад', r'меню', r'главная', r'каталог', r'поиск',
    r'авито', r'доставка\s+авито', r'безопасная\s+сделка',
    r'\+7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}',
    r'показать\s+телефон', r'показать\s+номер',
    r'москва,\s*ул\.', r'показать\s+на\s+карте',
    r'реклама', r'купить', r'заказать', r'кредит\s+от',
    r'рассрочка', r'лизинг', r'\d+,\d+\s+★', r'\d+\s+отзыв',
    r'рейтинг', r'отвечает\s+на\s+сообщения',
    r'похожие\s+объявления', r'сохранить',
]


def _crop_borders(img: Image.Image) -> Image.Image:
    """Обрезает верх и низ скриншота (кнопки/меню)"""
    width, height = img.size
    crop_top = int(height * 0.10)
    crop_bottom = int(height * 0.85)
    return img.crop((0, crop_top, width, crop_bottom))


def _preprocess_image(img: Image.Image) -> Image.Image:
    """Предобработка изображения для Tesseract"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Обрезаем кнопки
    img = _crop_borders(img)
    
    # Серый
    img = ImageOps.grayscale(img)
    
    # Увеличение x3
    scale = 3
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    
    # Контраст + резкость
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    
    # Threshold
    img = img.point(lambda x: 0 if x < 140 else 255, mode="1")
    
    return img


def _clean_text(text: str) -> str:
    """Постобработка: убираем мусор"""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        
        if not line_stripped or len(line_stripped) <= 2:
            continue
        
        # Проверяем на мусор
        is_garbage = False
        for pattern in GARBAGE_PATTERNS:
            if re.search(pattern, line_lower, re.IGNORECASE):
                is_garbage = True
                break
        
        if not is_garbage:
            cleaned_lines.append(line_stripped)
    
    text = '\n'.join(cleaned_lines)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def ocr_image_to_text(image_path: str) -> str:
    """
    Главная функция OCR.
    Использует Tesseract (быстро и стабильно).
    """
    if not TESSERACT_AVAILABLE:
        print("❌ Tesseract not available!")
        return ""
    
    try:
        print(f"🔍 Using Tesseract for {os.path.basename(image_path)}")
        
        img = Image.open(image_path)
        img_prep = _preprocess_image(img)
        
        # Tesseract конфиг
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(img_prep, lang="rus+eng", config=config)
        
        # Чистим мусор
        text = _clean_text(text)
        
        print(f"✅ Tesseract recognized {len(text)} chars")
        return text
        
    except Exception as e:
        print(f"❌ Tesseract failed: {e}")
        return ""
