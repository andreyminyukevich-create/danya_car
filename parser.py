#!/usr/bin/env python3
"""
Парсер описаний автомобилей для КП
Работает через regex + словари (без API)
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
            'mileage_km': None,  # Запросим у пользователя
            'price_rub': None,   # Запросим у пользователя
            'price_note': 'с НДС',
            'spec_items': self._extract_spec_items(text),
        }
        
        return result
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Извлекает название модели"""
        # Ищем "Вариант модели:" в начале
        match = re.search(r'Вариант модели:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Убираем лишнее ", Полный" и т.д.
            title = re.sub(r',\s*(Полный|Передний|Задний)$', '', title)
            return title
        
        # Ищем "Модификация:"
        match = re.search(r'Модификация\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Извлекает год выпуска"""
        # Ищем "Год" и список годов
        match = re.search(r'Год\s*(\d{4}(?:,\s*\d{4})*)', text)
        if match:
            years_str = match.group(1)
            # Берем последний (самый новый) год
            years = [int(y.strip()) for y in years_str.split(',')]
            return max(years)
        
        # Альтернативно: просто ищем 4 цифры 20XX
        matches = re.findall(r'\b(20\d{2})\b', text)
        if matches:
            return int(matches[-1])
        
        return None
    
    def _extract_drive(self, text_lower: str) -> Optional[str]:
        """Извлекает тип привода"""
        # Ищем в строке "Привод"
        match = re.search(r'Привод\s*([^\n]+)', text_lower)
        if match:
            drive_text = match.group(1).strip()
            for key, value in self.drive_types.items():
                if key in drive_text:
                    return value
        
        # Ищем по всему тексту
        for key, value in self.drive_types.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_engine(self, text: str) -> Optional[str]:
        """Извлекает описание двигателя (мощность + объем + тип)"""
        power = None
        volume = None
        engine_type = None
        
        # Мощность
        match = re.search(r'Мощность[,\s]*л\.с\.\s*(\d+)', text)
        if match:
            power = match.group(1)
        
        # Объем
        match = re.search(r'Объём двигателя[,\s]*л\s*([\d,\.]+)\s*л', text)
        if match:
            volume = match.group(1).replace(',', '.')
        
        # Тип двигателя
        text_lower = text.lower()
        match = re.search(r'Тип двигателя\s*([^\n]+)', text_lower)
        if match:
            type_text = match.group(1).strip()
            for key, value in self.engine_types.items():
                if key in type_text:
                    engine_type = value
                    break
        
        # Собираем строку
        parts = []
        if power:
            parts.append(f"{power} л.с.")
        if volume:
            parts.append(f"{volume}")
        if engine_type:
            parts.append(engine_type)
        
        if parts:
            return ', '.join(parts)
        
        return None
    
    def _extract_gearbox(self, text_lower: str) -> Optional[str]:
        """Извлекает тип коробки передач"""
        match = re.search(r'Коробка передач\s*([^\n]+)', text_lower)
        if match:
            gearbox_text = match.group(1).strip()
            for key, value in self.gearbox_types.items():
                if key in gearbox_text:
                    return value
        
        # Ищем по всему тексту
        for key, value in self.gearbox_types.items():
            if key in text_lower:
                return value
        
        return None
    
    def _extract_color(self, text_lower: str) -> Optional[str]:
        """Извлекает цвет (обычно нет в спецификации)"""
        for key, value in self.colors.items():
            if key in text_lower:
                return value
        return None
    
    def _extract_spec_items(self, text: str) -> List[str]:
        """
        Извлекает ключевые характеристики для раздела "Спецификация"
        """
        spec_items = []
        
        # Список важных характеристик для КП
        patterns = [
            (r'Объём двигателя[,\s]*л:\s*([^\n]+)', 'Объём двигателя, л: {}'),
            (r'Тип двигателя\s*([^\n]+)', 'Тип двигателя: {}'),
            (r'Мощность[,\s]*л\.с\.\s*(\d+)', 'Мощность, л.с.: {}'),
            (r'Коробка передач\s*([^\n]+)', 'Коробка передач: {}'),
            (r'Привод\s*([^\n]+)', 'Привод: {}'),
            (r'Разгон до 100 км/ч\s*([\d,\.]+\s*с)', 'Разгон до 100 км/ч: {}'),
            (r'Объём багажника\s*(\d+\s*л)', 'Объём багажника: {}'),
            (r'Рабочий объём\s*(\d+\s*см³)', 'Рабочий объём: {}'),
            (r'Количество цилиндров\s*(\d+)', 'Количество цилиндров: {}'),
            (r'Конфигурация двигателя\s*([^\n]+)', 'Конфигурация двигателя: {}'),
            (r'Крутящий момент\s*([\d\s]+Н⋅м)', 'Крутящий момент: {}'),
            (r'Расход топлива смешанный\s*([\d,\.]+\s*л/100 км)', 'Расход топлива: {}'),
            (r'Максимальная скорость\s*(\d+\s*км/ч)', 'Максимальная скорость: {}'),
            (r'Экологический класс\s*([^\n]+)', 'Экологический класс: {}'),
            (r'Ёмкость топливного бака\s*(\d+\s*л)', 'Ёмкость топливного бака: {}'),
            (r'Передняя подвеска\s*([^\n]+)', 'Передняя подвеска: {}'),
            (r'Задняя подвеска\s*([^\n]+)', 'Задняя подвеска: {}'),
            (r'Передние тормоза\s*([^\n]+)', 'Передние тормоза: {}'),
            (r'Задние тормоза\s*([^\n]+)', 'Задние тормоза: {}'),
            (r'Страна\s*([^\n]+)', 'Страна: {}'),
            (r'Кузов\s*([^\n]+)', 'Кузов: {}'),
            (r'Количество дверей\s*(\d+)', 'Количество дверей: {}'),
            (r'Рейтинг EuroNCAP\s*(\d+)', 'Рейтинг EuroNCAP: {}'),
        ]
        
        for pattern, template in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                spec_items.append(template.format(value))
        
        return spec_items
