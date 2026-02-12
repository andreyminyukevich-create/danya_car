#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR сервис на EasyOCR (нейросеть).
Точнее чем Tesseract для мобильных скриншотов Авито.
"""

from __future__ import annotations

import re
import os
from typing import Optional

from PIL import Image, ImageOps, ImageEnhance

# Пытаемся импортировать EasyOCR
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR not available, falling back to Tesseract")

# Fallback на Tesseract
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

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


# Глобальный reader (инициализируется один раз)
_easyocr_reader = None


def get_easyocr_reader():
    """Получить EasyOCR reader (инициализируется один раз)"""
    global _easyocr_reader
    
    if _easyocr_reader is None and EASYOCR_AVAILABLE:
        print("🔄 Initializing EasyOCR (first time only)...")
        _easyocr_reader = easyocr.Reader(
            ['ru', 'en'],
            gpu=False,  # CPU mode (Railway не даёт GPU)
            verbose=False
        )
        print("✅ EasyOCR initialized")
    
    return _easyocr_reader


def _crop_borders(img: Image.Image) -> Image.Image:
    """Обрезает верх и низ скриншота (кнопки/меню)"""
    width, height = img.size
    crop_top = int(height * 0.10)
    crop_bottom = int(height * 0.85)
    return img.crop((0, crop_top, width, crop_bottom))


def _preprocess_for_easyocr(img: Image.Image) -> Image.Image:
    """Лёгкая предобработка для EasyOCR (нейросеть сама справится)"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    # Обрезаем кнопки
    img = _crop_borders(img)
    
    # Увеличение x2 (EasyOCR любит больше пикселей)
    scale = 2
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    
    return img


def _preprocess_for_tesseract(img: Image.Image) -> Image.Image:
    """Агрессивная предобработка для Tesseract"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    
    img = _crop_borders(img)
    img = ImageOps.grayscale(img)
    
    scale = 3
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
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
    Использует EasyOCR (нейросеть) если доступен, иначе Tesseract.
    """
    img = Image.open(image_path)
    
    # Приоритет 1: EasyOCR (лучшая точность)
    if EASYOCR_AVAILABLE:
        try:
            print(f"🔍 Using EasyOCR for {os.path.basename(image_path)}")
            
            # Лёгкая предобработка
            img_prep = _preprocess_for_easyocr(img)
            
            # Сохраняем временно для EasyOCR
            temp_path = image_path.replace('.jpg', '_prep.jpg')
            img_prep.save(temp_path)
            
            # EasyOCR
            reader = get_easyocr_reader()
            results = reader.readtext(temp_path, detail=0, paragraph=True)
            
            # Склеиваем результаты
            text = '\n'.join(results)
            
            # Удаляем временный файл
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            # Чистим мусор
            text = _clean_text(text)
            
            print(f"✅ EasyOCR recognized {len(text)} chars")
            return text
            
        except Exception as e:
            print(f"❌ EasyOCR failed: {e}, falling back to Tesseract")
    
    # Приоритет 2: Tesseract (fallback)
    if TESSERACT_AVAILABLE:
        try:
            print(f"🔍 Using Tesseract for {os.path.basename(image_path)}")
            
            img_prep = _preprocess_for_tesseract(img)
            
            config = "--oem 3 --psm 6"
            text = pytesseract.image_to_string(img_prep, lang="rus+eng", config=config)
            text = _clean_text(text)
            
            print(f"✅ Tesseract recognized {len(text)} chars")
            return text
            
        except Exception as e:
            print(f"❌ Tesseract failed: {e}")
            return ""
    
    # Если ничего не работает
    print("❌ No OCR engine available!")
    return ""
