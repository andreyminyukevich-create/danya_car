#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCR сервис на локальном Tesseract.
Распознаёт русский + английский.
"""

from __future__ import annotations

import re
from typing import Optional

import pytesseract
from PIL import Image, ImageOps, ImageEnhance

try:
    import cv2  # opencv-python-headless
    import numpy as np
except Exception:
    cv2 = None
    np = None


def _preprocess_pil(img: Image.Image) -> Image.Image:
    """
    Базовая предобработка, работает всегда (без OpenCV).
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Серый
    img = ImageOps.grayscale(img)

    # Увеличение (часто очень помогает таблицам)
    scale = 2
    img = img.resize((img.width * scale, img.height * scale))

    # Контраст + резкость
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(1.6)

    # Лёгкий порог (черно-белое)
    img = img.point(lambda x: 0 if x < 160 else 255, mode="1")

    return img


def _preprocess_opencv(img: Image.Image) -> Image.Image:
    """
    Улучшенная предобработка (если есть OpenCV).
    """
    if cv2 is None or np is None:
        return _preprocess_pil(img)

    if img.mode != "RGB":
        img = img.convert("RGB")

    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    # Увеличение
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # Шум чуть убираем
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Адаптивный threshold под разный фон
    thr = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11
    )

    return Image.fromarray(thr)


def _normalize_text(text: str) -> str:
    """
    Мини-нормализация OCR-выхода: пробелы, странные переносы.
    """
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ocr_image_to_text(image_path: str) -> str:
    """
    Главная функция OCR: принимает путь к картинке, возвращает распознанный текст.
    """
    img = Image.open(image_path)

    # Сначала пробуем OpenCV-предобработку, если есть
    img_prep = _preprocess_opencv(img)

    # Tesseract config
    # PSM 6: "один блок текста" — обычно хорошо для таблиц/характеристик
    config = "--oem 3 --psm 6"

    text = pytesseract.image_to_string(img_prep, lang="rus+eng", config=config)
    return _normalize_text(text)
