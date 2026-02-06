#!/usr/bin/env python3
"""
Парсер описаний автомобилей для КП
Понимает ЛЮБОЙ копипаст с Авито (даже с мусором)
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
            '4matic': 'Полный',
            'fwd': 'Передний',
            'rwd': 'Задний',
            'quattro': 'Полный',
            '4x4': 'Полный',
            'xdrive': 'Полный',
        }
        
        self.gearbox_types = {
            'автомат': 'Автомат',
            'механика': 'Механика',
            'робот': 'Робот',
            'вариатор': 'Вариатор',
            'at': 'Автомат',
            'amt': 'Автомат',
            'mt': 'Механика',
            'cvt': 'Вариатор',
            'dsg': 'Робот',
            'steptronic': 'Автомат',
            'g-tronic': 'Автомат',
            '9g-tronic': 'Автомат',
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
            'фиолетовый': 'Фиолетовый',
        }
        
        # Список "мусора" из Авито
        self.garbage_keywords = [
            'для бизнеса', 'карьера', 'помощь', 'каталоги', 'мои объявления',
            'сообщения', 'главная', 'транспорт', 'автомобили', 'новые',
            'аватар', 'все характеристики', 'расположение', 'описание',
            'дополнительные опции', 'стоимость владения', 'другие объявления',
            'а это наш журнал', 'безопасность', 'реклама на сайте',
            'политика конфиденциальности', 'правила авито', 'оферту',
            'показать карту', 'изменить регион', 'спросите у продавца',
            'контактное лицо', 'компания', 'свежие объявления', 'кредит',
            'ежемесячный платёж', 'автотека', 'нейросеть', 'оценка'
        ]
    
    def parse(self, text: str) -> Dict:
        """
        Основная функция парсинга
        Возвращает словарь с извлеченными данными
        """
        try:
            # Очищаем текст от мусора
            cleaned_text = self._clean_text(text)
            text_lower = cleaned_text.lower()
            
            result = {
                'title': self._safe_extract(self._extract_title, cleaned_text),
                'year': self._safe_extract(self._extract_year, cleaned_text),
                'drive': self._safe_extract(self._extract_drive, text_lower),
                'engine_short': self._safe_extract(self._extract_engine, cleaned_text),
                'gearbox': self._safe_extract(self._extract_gearbox, text_lower),
                'color': self._safe_extract(self._extract_color, text_lower),
                'mileage_km': self._safe_extract(self._extract_mileage, cleaned_text),
                'price_rub': None,  # НЕ парсим - будем запрашивать
                'price_note': 'с НДС',
                'spec_items': self._safe_extract(self._extract_spec_items, cleaned_text, default=[]),
            }
            
            return result
            
        except Exception as e:
            print(f"Critical error in parser: {e}")
            # Возвращаем пустую структуру
            return {
                'title': None,
                'year': None,
                'drive': None,
                'engine_short': None,
                'gearbox': None,
                'color': None,
                'mileage_km': None,
                'price_rub': None,
                'price_note': 'с НДС',
                'spec_items': [],
            }
    
    def _safe_extract(self, func, text, default=None):
        """Безопасное выполнение функции извлечения"""
        try:
            return func(text)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return default
    
    def _clean_text(self, text: str) -> str:
        """Убирает мусор из копипаста"""
        try:
            lines = text.split('\n')
            clean_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                line_lower = line_stripped.lower()
                
                # Пропускаем пустые строки
                if not line_stripped:
                    continue
                
                # Пропускаем мусор
                is_garbage = False
                for keyword in self.garbage_keywords:
                    if keyword in line_lower:
                        is_garbage = True
                        break
                
                # Пропускаем короткие строки с только цифрами/символами
                if len(line_stripped) < 10 and re.match(r'^[\d\s:—·±]+$', line_stripped):
                    is_garbage = True
                
                # Пропускаем строки с иконками/эмодзи
                if any(char in line_stripped for char in ['◾', '▪', '✅', '●', '·', '…', '⋮']):
                    is_garbage = True
                
                if not is_garbage:
                    clean_lines.append(line_stripped)
            
            return '\n'.join(clean_lines)
        except:
            return text
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Извлекает название (марка + модель + модификация)"""
        
        # Шаг 1: Находим основное название (формат Авито)
        # "Toyota Land Cruiser 4.6 AT, 2015, 182 800 км"
        match = re.search(r'([A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)*(?:\s+[A-Z0-9\-]+)*)\s+(\d\.\d+)\s+([A-Z]{2,})(?:,\s*\d{4})?', text)
        if match:
            brand_model = match.group(0).strip()
            # Убираем год и пробег
            brand_model = re.sub(r',\s*\d{4}.*$', '', brand_model)
            return brand_model
        
        # Вариант 2: Ищем известные бренды
        brands = [
            'Mercedes-Benz', 'Mercedes', 'Land Rover', 'Range Rover',
            'BMW', 'Audi', 'Porsche', 'Toyota', 'Lexus', 'Volkswagen',
            'Volvo', 'Tesla', 'Ford', 'Chevrolet', 'Nissan', 'Honda',
            'Mazda', 'Hyundai', 'Kia', 'Subaru', 'Mitsubishi',
            'Jaguar', 'Bentley', 'Rolls-Royce', 'Cadillac', 'Lamborghini',
            'Ferrari', 'Maserati', 'Aston Martin', 'McLaren', 'Jeep'
        ]
        
        for brand in brands:
            pattern = rf'\b{re.escape(brand)}\s+([A-Za-z0-9\s\-]+?)(?:\s+\d\.\d+|\s+AT|\s+MT|,|\n|$)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = match.group(0).strip()
                result = re.sub(r',\s*\d{4}.*$', '', result)
                return result
        
        # Вариант 3: Берём модификацию
        modification = self._extract_modification(text)
        if modification:
            return modification
        
        return None
    
    def _extract_modification(self, text: str) -> Optional[str]:
        """Извлекает модификацию"""
        match = re.search(r'Модификация:\s*([^\n]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_year(self, text: str) -> Optional[int]:
        """Извлекает год"""
        # Приоритет: "Год выпуска:"
        match = re.search(r'Год\s+выпуска:\s*(\d{4})', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Ищем год в диапазоне 2000-2030
        matches = re.findall(r'\b(20[0-2]\d|199\d)\b', text)
        if matches:
            years = [int(y) for y in matches if 2000 <= int(y) <= 2030]
            if years:
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
        
        # Ищем в тексте
        for key, value in self.drive_types.items():
            if re.search(rf'\b{key}\b', text_lower):
                return value
        
        return None
    
    def _extract_engine(self, text: str) -> Optional[str]:
        """Извлекает двигатель (мощность + объем + тип)"""
        power = None
        volume = None
        engine_type = None
        
        # Мощность
        match = re.search(r'(\d{2,4})\s*л\.?\s*с\.?', text, re.IGNORECASE)
        if match:
            power = match.group(1)
        
        # Объем
        match = re.search(r'(?:Объём двигателя:\s*)?([\d,\.]+)\s*л(?:\s|,|$)', text, re.IGNORECASE)
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
        
        # Ищем в тексте
        for key, value in self.gearbox_types.items():
            if re.search(rf'\b{re.escape(key)}\b', text_lower):
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
        
        # Ищем в тексте
        for key, value in self.colors.items():
            if re.search(rf'\b{key}\b', text_lower):
                return value
        
        return None
    
    def _extract_mileage(self, text: str) -> Optional[int]:
        """Извлекает пробег"""
        text_lower = text.lower()
        
        # Новый автомобиль
        if 'новый' in text_lower or 'новая' in text_lower or 'новое' in text_lower:
            return 0
        
        # Приоритет 1: "Пробег: 182 800 км"
        match = re.search(r'Пробег:\s*([\d\s]+)\s*км', text, re.IGNORECASE)
        if match:
            mileage_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                mileage = int(mileage_str)
                if 0 <= mileage <= 1000000:
                    return mileage
            except:
                pass
        
        # Приоритет 2: В заголовке "Toyota Land Cruiser 4.6 AT, 2015, 182 800 км"
        # Ищем: запятая, год, запятая, число, км
        match = re.search(r',\s*\d{4},\s*([\d\s]+)\s*км', text)
        if match:
            mileage_str = match.group(1).replace(' ', '').replace(',', '')
            try:
                mileage = int(mileage_str)
                if 10 <= mileage <= 1000000:
                    return mileage
            except:
                pass
        
        # Приоритет 3: Просто первое число + км (но не маленькое)
        matches = re.findall(r'(\d[\d\s,]*)\s*км', text_lower)
        for match_str in matches:
            mileage_str = match_str.replace(' ', '').replace(',', '')
            try:
                mileage = int(mileage_str)
                # Адекватный пробег (не путаем с другими числами типа "13 700 км в год")
                if 100 <= mileage <= 1000000:
                    return mileage
            except:
                pass
        
        return None
    
    def _extract_spec_items(self, text: str) -> List[str]:
        """Извлекает спецификацию"""
        spec_items = []
        
        patterns = [
            (r'Поколение:\s*([^\n]+)', 'Поколение: {}'),
            (r'Модификация:\s*([^\n]+)', 'Модификация: {}'),
            (r'Объём двигателя:\s*([^\n]+)', 'Объём двигателя: {}'),
            (r'Тип двигателя:\s*([^\n]+)', 'Тип двигателя: {}'),
            (r'Коробка передач:\s*([^\n]+)', 'Коробка передач: {}'),
            (r'Привод:\s*([^\n]+)', 'Привод: {}'),
            (r'Комплектация:\s*([^\n]+)', 'Комплектация: {}'),
            (r'Тип кузова:\s*([^\n]+)', 'Тип кузова: {}'),
            (r'Руль:\s*([^\n]+)', 'Руль: {}'),
            (r'ПТС:\s*([^\n]+)', 'ПТС: {}'),
            (r'Состояние:\s*([^\n]+)', 'Состояние: {}'),
        ]
        
        for pattern, template in patterns:
            try:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    spec_items.append(template.format(value))
            except:
                pass
        
        return spec_items
