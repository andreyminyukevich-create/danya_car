#!/usr/bin/env python3
"""
Парсер описаний автомобилей для КП
Понимает ЛЮБОЙ формат копипаста с Авито
"""

import re
from typing import Dict, Optional, List


class CarDescriptionParser:
    """Парсит описание автомобиля и извлекает нужные поля"""
    
    def __init__(self):
        # Словари для распознавания
        self.drive_types = {
            'полный': 'Полный',
            'передний': 'Передний',
            'задний': 'Задний',
            '4wd': 'Полный',
            'awd': 'Полный',
            'fwd': 'Передний',
            'rwd': 'Задний',
            'quattro': 'Полный',
            '4x4': 'Полный',
        }
        
        self.gearbox_types = {
            'автомат': 'Автомат',
            'механика': 'Механика',
            'робот': 'Робот',
            'вариатор': 'Вариатор',
            'at': 'Автомат',
            'mt': 'Механика',
            'amt': 'Робот',
            'cvt': 'Вариатор',
            'dsg': 'Робот',
            'steptronic': 'Автомат',
        }
        
        self.engine_types = {
            'бензин': 'Бензин',
            'дизель': 'Дизель',
            'гибрид': 'Гибрид',
            'электро': 'Электро',
            'diesel': 'Дизель',
            'petrol': 'Бензин',
            'hybrid': 'Гибрид',
            'electric': 'Электро',
        }
        
        self.colors = {
            'белый': 'Белый',
            'черный': 'Черный',
            'серый': 'Серый',
            'серебристый': 'Серебристый',
            'красный': 'Красный',
            'синий': 'Синий',
            'зеленый': 'Зеленый',
            'коричневый': 'Коричневый',
            'бежевый': 'Бежевый',
            'золотой': 'Золотой',
            'оранжевый': 'Оранжевый',
        }
    
    def parse(self, text: str) -> Dict:
        """
        Основная функция парсинга
        Возвращает словарь с извлеченными данными
        """
        text_lower = text.lower()
        
        result = {
            'title': self._extract_title(text),
            'year': self._extract_year(text),
            'drive': self._extract_drive(text_lower),
            'engine_short': self._extract_engine(text),
            'gearbox': self._extract_gearbox(text_lower),
            'color': self._extract_color(text_lower),
            'mileage_km': self._extract_mileage(text),
            'price_rub': None,
            'price_note': 'с НДС',
            'spec_items': self._extract_spec_items(text),
        }
        
        return result
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Извлекает название (марка + модель + модификация)"""
        
        # Шаг 1: Находим марку и модель
        brand_model = None
        
        # Вариант 1: Ищем известные марки в начале текста
        brands = [
            'Land Rover', 'Range Rover', 'BMW', 'Mercedes-Benz', 'Mercedes', 
            'Audi', 'Porsche', 'Toyota', 'Lexus', 'Volkswagen', 'Volvo',
            'Tesla', 'Ford', 'Chevrolet', 'Nissan', 'Honda', 'Mazda',
            'Hyundai', 'Kia', 'Subaru', 'Mitsubishi', 'Jaguar',
            'Bentley', 'Rolls-Royce', 'Lamborghini', 'Ferrari', 'Maserati'
        ]
        
        for brand in brands:
            # Ищем бренд + что-то после него (модель)
            pattern = rf'\b{re.escape(brand)}\s+([A-Za-z0-9\s-]+?)(?:\s+\d\.\d+|\s+AT|\s+MT|,|\d{{4}}|$)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                brand_model = match.group(0).strip()
                # Убираем год в конце
                brand_model = re.sub(r',?\s*\d{4}$', '', brand_model)
                break
        
        # Вариант 2: Ищем перед "Характеристики"
        if not brand_model:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                if 'характеристики' in line.lower():
                    # Ищем подходящую строку выше
                    for j in range(max(0, i-5), i):
                        candidate = lines[j]
                        # Должна содержать буквы и быть достаточно длинной
                        if len(candidate) > 10 and re.search(r'[A-Za-z]', candidate):
                            # Не должна быть мусором (кнопки, меню)
                            if not any(x in candidate.lower() for x in ['помощь', 'каталог', 'объявлени', 'сообщени', 'поиск']):
                                brand_model = candidate
                                brand_model = re.sub(r',?\s*\d{4}.*$', '', brand_model)
                                break
                    if brand_model:
                        break
        
        # Шаг 2: Добавляем модификацию если есть
        modification = None
        
        # Ищем "Модификация:"
        match = re.search(r'Модификация:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            modification = match.group(1).strip()
        
        # Или ищем модификацию в самом названии (P530, 30i, 40d и т.д.)
        if not modification and brand_model:
            mod_match = re.search(r'\b([A-Z]?\d{2,4}[a-z]?(?:\s+\d\.\d+)?(?:\s+[A-Z]{2,})?(?:\s+\([^\)]+\))?)', text)
            if mod_match:
                modification = mod_match.group(1)
        
        # Собираем итоговое название
        if brand_model and modification:
            return f"{brand_model} {modification}"
        elif brand_model:
            return brand_model
        elif modification:
            return modification
        
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Извлекает год"""
        # Приоритет 1: "Год выпуска:"
        match = re.search(r'Год\s+выпуска:\s*(\d{4})', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Приоритет 2: Ищем 20XX рядом с другими данными
        matches = re.findall(r'\b(20\d{2})\b', text)
        if matches:
            # Берём самый свежий год
            years = [int(y) for y in matches]
            return max(years)
        
        return None
    
    def _extract_drive(self, text_lower: str) -> Optional[str]:
        """Извлекает привод"""
        match = re.search(r'Привод:\s*([^\n]+)', text_lower)
        if match:
            drive_text = match.group(1).strip()
            for key, value in self.drive_types.items():
                if key in drive_text:
                    return value
        
        for key, value in self.drive_types.items():
            if f' {key} ' in f' {text_lower} ' or f' {key},' in text_lower or f' {key}\n' in text_lower:
                return value
        
        return None
    
    def _extract_engine(self, text: str) -> Optional[str]:
        """Извлекает двигатель"""
        power = None
        volume = None
        engine_type = None
        
        # Мощность - ищем в скобках (530 л.с.) или отдельно
        match = re.search(r'(\d{2,4})\s*л\.?\s*с\.?', text, re.IGNORECASE)
        if match:
            power = match.group(1)
        
        # Объем - "4.4 л" или "Объём двигателя: 4.4 л"
        match = re.search(r'(?:Объём двигателя:\s*)?([\d,\.]+)\s*л(?:\s|$|,)', text, re.IGNORECASE)
        if match:
            volume = match.group(1).replace(',', '.')
        
        # Тип двигателя
        text_lower = text.lower()
        match = re.search(r'Тип двигателя:\s*([^\n]+)', text_lower)
        if match:
            type_text = match.group(1).strip()
            for key, value in self.engine_types.items():
                if key in type_text:
                    engine_type = value
                    break
        
        # Собираем
        parts = []
        if power:
            parts.append(f"{power} л.с.")
        if volume:
            parts.append(f"{volume}л")
        if engine_type:
            parts.append(engine_type)
        
        return ', '.join(parts) if parts else None
    
    def _extract_gearbox(self, text_lower: str) -> Optional[str]:
        """Извлекает КПП"""
        match = re.search(r'Коробка передач:\s*([^\n]+)', text_lower)
        if match:
            gearbox_text = match.group(1).strip()
            for key, value in self.gearbox_types.items():
                if key in gearbox_text:
                    return value
        
        # Ищем AT/MT в названии
        if ' at' in text_lower or ' at,' in text_lower or ' at ' in text_lower:
            return 'Автомат'
        if ' mt' in text_lower or ' mt,' in text_lower or ' mt ' in text_lower:
            return 'Механика'
        
        for key, value in self.gearbox_types.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_color(self, text_lower: str) -> Optional[str]:
        """Извлекает цвет"""
        match = re.search(r'Цвет:\s*([^\n]+)', text_lower)
        if match:
            color_text = match.group(1).strip()
            for key, value in self.colors.items():
                if key in color_text:
                    return value
        
        for key, value in self.colors.items():
            if f' {key}' in text_lower or f'{key} ' in text_lower:
                return value
        
        return None
    
    def _extract_mileage(self, text: str) -> Optional[int]:
        """Извлекает пробег"""
        if 'новый' in text.lower() or 'новая' in text.lower() or 'новое' in text.lower():
            return 0
        
        # Ищем пробег
        match = re.search(r'(\d[\d\s]*)\s*км', text.lower())
        if match:
            mileage_str = match.group(1).replace(' ', '')
            mileage = int(mileage_str)
            # Если меньше 1000, значит в тысячах (50 км = 50000)
            if mileage < 1000:
                mileage *= 1000
            return mileage
        
        return None
    
    def _extract_spec_items(self, text: str) -> List[str]:
        """Извлекает спецификацию"""
        spec_items = []
        
        patterns = [
            (r'Объём двигателя:\s*([^\n]+)', 'Объём двигателя: {}'),
            (r'Тип двигателя:\s*([^\n]+)', 'Тип двигателя: {}'),
            (r'Мощность[,\s]*л\.?с\.?:\s*(\d+)', 'Мощность, л.с.: {}'),
            (r'Коробка передач:\s*([^\n]+)', 'Коробка передач: {}'),
            (r'Привод:\s*([^\n]+)', 'Привод: {}'),
            (r'Комплектация:\s*([^\n]+)', 'Комплектация: {}'),
            (r'Тип кузова:\s*([^\n]+)', 'Тип кузова: {}'),
            (r'Поколение:\s*([^\n]+)', 'Поколение: {}'),
            (r'Руль:\s*([^\n]+)', 'Руль: {}'),
        ]
        
        for pattern, template in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                spec_items.append(template.format(value))
        
        return spec_items
