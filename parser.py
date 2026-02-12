#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Парсер описаний автомобилей с Авито
ФИНАЛЬНАЯ ВЕРСИЯ: белый список + только поля со значениями
"""

import re
from typing import Dict, Optional, List


class CarDescriptionParser:
    """Парсер описаний автомобилей"""
    
    def __init__(self):
        # Словарь цветов
        self.colors = {
            'белый', 'чёрный', 'черный', 'серый', 'серебристый', 'серебряный',
            'красный', 'синий', 'зелёный', 'зеленый', 'коричневый', 'бежевый',
            'золотой', 'оранжевый', 'фиолетовый', 'жёлтый', 'желтый',
            'бордовый', 'розовый', 'голубой', 'салатовый'
        }
        
        # БЕЛЫЙ СПИСОК: допустимые ключевые слова
        self.spec_keywords = [
            # Двигатель
            'двигател', 'объём', 'объем', 'тип двигател', 'мощность', 'л.с',
            'цилиндр', 'конфигурац', 'рабочий объём', 'крутящий момент',
            'оборот', 'максимальн',
            
            # Трансмиссия
            'коробка', 'передач', 'привод', 'трансмисси',
            
            # Размеры
            'длина', 'ширина', 'высота', 'база', 'колёсная база', 'колесная база',
            'просвет', 'дорожный просвет', 'диаметр', 'разворот', 'колея',
            'багажник', 'объём багажник', 'объем багажник',
            
            # Эксплуатационные
            'расход', 'топлив', 'разгон', 'скорость', 'максимальная скорость',
            'экологич', 'класс', 'ёмкость', 'емкость', 'бак', 'топливного бака',
            'марка топлива',
            
            # Подвеска и тормоза
            'подвеска', 'тормоз', 'передн', 'задн',
            
            # Шины и диски
            'шины', 'диски', 'размерность', 'колёса', 'колеса', 'крепёж', 'pcd',
            'центральное отверстие', 'dia',
            
            # Аккумулятор и масло
            'аккумулятор', 'пусковой ток', 'полярность', 'моторное масло',
            'sae', 'acea', 'api',
            
            # Кузов
            'кузов', 'тип кузова', 'двер', 'количество двер',
            
            # Идентификация
            'vin', 'птс', 'модификац', 'комплектац', 'рейтинг', 'euronсap',
            'вариант модели',
            
            # Общее
            'год', 'страна', 'цвет', 'руль', 'пробег', 'обмен'
        ]
    
    def _clean_title(self, text: str) -> Optional[str]:
        """Извлекает название автомобиля БЕЗ цены"""
        # Убираем цену из начала
        text_clean = re.sub(r'^\d+[\s\d]*[О0оo]*\s*₽?\s*', '', text)
        
        # Ищем паттерн: "Марка Модель"
        patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z0-9][A-Za-z0-9]*)+(?:\s+[\d\.]+)?(?:\s+[A-Z]+)?)',
            r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ0-9][А-Яа-яё0-9]*)+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_clean)
            if match:
                title = match.group(1).strip()
                # Убираем год если он в конце названия
                title = re.sub(r',?\s*\d{4}\s*$', '', title)
                # Убираем "км" и пробег
                title = re.sub(r',?\s*\d+[\s\d]*км.*$', '', title, flags=re.IGNORECASE)
                return title.strip()
        
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Извлекает год выпуска"""
        text_lower = text.lower()
        
        # Приоритет 1: "Год выпуска: 2021"
        match = re.search(r'год\s*выпуска[:\s]+(\d{4})', text_lower)
        if match:
            return int(match.group(1))
        
        # Приоритет 2: год в названии/начале
        match = re.search(r'\b(20[0-2]\d)\b', text[:200])
        if match:
            year = int(match.group(1))
            if 2000 <= year <= 2026:
                return year
        
        return None
    
    def _extract_drive(self, text: str) -> Optional[str]:
        """Извлекает привод"""
        text_lower = text.lower()
        
        if re.search(r'полн(ый|ая)', text_lower):
            return "Полный"
        if re.search(r'перед(ний|няя)', text_lower):
            return "Передний"
        if re.search(r'задн(ий|яя)', text_lower):
            return "Задний"
        
        return None
    
    def _extract_engine(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Извлекает двигатель"""
        text_lower = text.lower()
        
        # Ищем мощность (л.с.)
        power_match = re.search(r'(\d+)\s*л\.?\s*с', text_lower)
        power = int(power_match.group(1)) if power_match else None
        
        # Ищем объём (НЕ ПУТАТЬ С МОЩНОСТЬЮ!)
        volume = None
        
        # Приоритет 1: "Объём двигателя: 3 л"
        vol_match = re.search(r'объ[её]м\s*двигателя[:\s,]*(\d+\.?\d*)\s*л', text_lower)
        if vol_match:
            volume = float(vol_match.group(1))
        
        # Приоритет 2: "3.0л", "3л" (фильтр 0.6-9.0л)
        if not volume:
            vol_match = re.search(r'\b(\d{1,2}\.?\d?)\s*л\b', text_lower)
            if vol_match:
                vol_candidate = float(vol_match.group(1))
                if 0.6 <= vol_candidate <= 9.0:
                    volume = vol_candidate
        
        # Тип топлива
        fuel_type = None
        if re.search(r'бензин', text_lower):
            fuel_type = "Бензин"
        elif re.search(r'дизел', text_lower):
            fuel_type = "Дизель"
        elif re.search(r'электр', text_lower):
            fuel_type = "Электро"
        elif re.search(r'гибрид', text_lower):
            fuel_type = "Гибрид"
        
        # Формируем описание
        parts = []
        if power:
            parts.append(f"{power} л.с.")
        if volume:
            parts.append(f"{volume:.1f}л".replace('.0', ''))
        if fuel_type:
            parts.append(fuel_type)
        
        engine_short = ", ".join(parts) if parts else None
        return engine_short, engine_short
    
    def _extract_gearbox(self, text: str) -> Optional[str]:
        """Извлекает коробку передач"""
        text_lower = text.lower()
        
        if re.search(r'автомат', text_lower):
            return "Автомат"
        if re.search(r'механик', text_lower):
            return "Механика"
        if re.search(r'робот', text_lower):
            return "Робот"
        if re.search(r'вариатор', text_lower):
            return "Вариатор"
        
        return None
    
    def _extract_color(self, text: str) -> Optional[str]:
        """Извлекает цвет"""
        text_lower = text.lower()
        original_text = text
        
        # Приоритет 1: "Цвет: Чёрный"
        color_match = re.search(r'цвет[:\s]+([а-яё]+)', text_lower, re.IGNORECASE)
        if color_match:
            color_word = color_match.group(1).lower()
            if color_word in self.colors:
                return color_word.capitalize()
        
        # Приоритет 2: поиск цвета как целого слова
        for color in self.colors:
            if re.search(r'\b' + color + r'\b', text_lower):
                match = re.search(r'\b' + color + r'\b', text_lower, re.IGNORECASE)
                if match:
                    start = match.start()
                    end = match.end()
                    return original_text[start:end].capitalize()
        
        return None
    
    def _extract_mileage(self, text: str) -> Optional[int]:
        """Извлекает пробег"""
        text_lower = text.lower()
        
        # Приоритет 1: "Пробег: 29800 км"
        match = re.search(r'пробег[:\s]+(\d+[\s\d]*)\s*км', text_lower)
        if match:
            mileage_str = match.group(1).replace(' ', '')
            return int(mileage_str)
        
        # Приоритет 2: просто число + км
        match = re.search(r'(\d+[\s\d]*)\s*км', text_lower)
        if match:
            mileage_str = match.group(1).replace(' ', '')
            mileage = int(mileage_str)
            if 0 <= mileage <= 1000000:
                return mileage
        
        return None
    
    def _is_valid_spec_item(self, line: str) -> bool:
        """
        ПРАВИЛО: ключевое слово + ЗНАЧЕНИЕ обязательно!
        Без значения (просто "Экологический класс") - мусор!
        """
        line_lower = line.lower().strip()
        
        # 1. Минимальная длина
        if len(line_lower) < 3:
            return False
        
        # 2. Есть число с единицей? → валидно
        units_pattern = r'\d+[\s\.,]*\d*\s*(км|л\.?с\.?|л|мм|м|c|см³|см|н\.?м|кг|км/ч|л/100\s*км|ач|а|об/мин)'
        if re.search(units_pattern, line_lower, re.IGNORECASE):
            return True
        
        # 3. Формат шин/дисков? → валидно
        if re.search(r'\d{3}/\d{2}', line) or re.search(r'\d+jx\d+', line_lower):
            return True
        
        # 4. VIN? → валидно
        if 'vin' in line_lower or re.search(r'[A-Z]{4,}', line):
            return True
        
        # 5. Есть ключевое слово из белого списка?
        has_keyword = any(keyword in line_lower for keyword in self.spec_keywords)
        
        if has_keyword:
            # КРИТИЧНО: проверяем что есть ЗНАЧЕНИЕ!
            
            # Есть двоеточие и текст после?
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2 and parts[1].strip():
                    return True
            
            # Есть число?
            if re.search(r'\d+', line):
                return True
            
            # Есть известные значения (привод, топливо и тд)?
            known_values = [
                'полный', 'передний', 'задний', 'автомат', 'механика', 
                'робот', 'вариатор', 'бензин', 'дизель', 'электро',
                'независима', 'зависима', 'дисковые', 'барабанные',
                'рядный', 'v-образный', 'euro', 'китай', 'германия',
                'япония', 'россия', 'корея', 'сша', 'франция', 'швеция',
                'пружинная', 'пневматическая', 'обратная', 'прямая'
            ]
            if any(val in line_lower for val in known_values):
                return True
            
            # Строка длинная? (вероятно описание)
            if len(line) > 25:
                return True
            
            # ТОЛЬКО ключевое слово без значения → МУСОР!
            return False
        
        # Нет ключевого слова → мусор
        return False
    
    def _extract_spec_items(self, text: str) -> List[str]:
        """
        Извлекает спецификацию.
        БЕЛЫЙ СПИСОК: только поля со значениями!
        """
        lines = text.split('\n')
        spec_items = []
        
        for line in lines:
            line = line.strip()
            
            # Убираем маркеры
            line = re.sub(r'^[•\-\*]\s*', '', line)
            
            if not line:
                continue
            
            # Проверяем валидность
            if not self._is_valid_spec_item(line):
                continue
            
            # Пропускаем основные поля (уже извлечены)
            line_lower = line.lower()
            skip_keywords = [
                'год выпуска:', 'пробег:', 'привод:', 'коробка передач:',
                'цвет:', 'мощность, л.с:', 'объём двигателя,'
            ]
            if any(keyword in line_lower for keyword in skip_keywords):
                continue
            
            spec_items.append(line)
        
        return spec_items
    
    def parse(self, text: str) -> Dict:
        """
        Парсит текст и возвращает структурированные данные
        """
        text = text.strip()
        
        # Извлекаем данные
        title = self._clean_title(text)
        year = self._extract_year(text)
        drive = self._extract_drive(text)
        engine_short, engine_full = self._extract_engine(text)
        gearbox = self._extract_gearbox(text)
        color = self._extract_color(text)
        mileage = self._extract_mileage(text)
        spec_items = self._extract_spec_items(text)
        
        return {
            'title': title,
            'year': year,
            'drive': drive,
            'engine_short': engine_short,
            'engine_full': engine_full,
            'gearbox': gearbox,
            'color': color,
            'mileage_km': mileage,
            'spec_items': spec_items,
        }
