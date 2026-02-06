#!/usr/bin/env python3
"""
Логирование КП в Google Sheets
"""

import os
import json
import logging
from datetime import datetime
import gspread
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

# ID таблицы из URL
SPREADSHEET_ID = "19QuydYq_boXdTmE1HFIGrM3AEWQaFwJ2_XnN-4SodPk"


class SheetsLogger:
    """Класс для логирования в Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.sheet = None
        self._connect()
    
    def _connect(self):
        """Подключение к Google Sheets"""
        try:
            # Получаем JSON из переменной окружения
            creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            
            if not creds_json:
                logger.warning("GOOGLE_CREDENTIALS_JSON not found - logging disabled")
                return
            
            # Парсим JSON
            creds_dict = json.loads(creds_json)
            
            # Создаём credentials
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=scope
            )
            
            # Подключаемся
            self.client = gspread.authorize(credentials)
            self.sheet = self.client.open_by_key(SPREADSHEET_ID).sheet1
            
            logger.info("✅ Connected to Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Google Sheets: {e}")
            self.client = None
            self.sheet = None
    
    def log_kp(self, user_id: int, username: str, car_data: dict, photos_count: int):
        """
        Логирует созданное КП в таблицу
        
        Args:
            user_id: Telegram user ID
            username: Имя пользователя
            car_data: Данные автомобиля
            photos_count: Количество фото
        """
        if not self.sheet:
            logger.warning("Sheets not connected - skipping log")
            return
        
        try:
            # Форматируем данные
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = car_data.get('title', '—')
            year = car_data.get('year', '—')
            price = car_data.get('price_rub', '—')
            price_note = car_data.get('price_note', '—')
            drive = car_data.get('drive', '—')
            
            # Форматируем цену
            if isinstance(price, int):
                price = f"{price:,}".replace(',', ' ')
            
            # Добавляем строку в таблицу
            row = [
                timestamp,
                user_id,
                username,
                title,
                year,
                price,
                price_note,
                drive,
                photos_count
            ]
            
            self.sheet.append_row(row)
            logger.info(f"✅ Logged KP to Sheets: {title} ({year})")
            
        except Exception as e:
            logger.error(f"❌ Failed to log to Sheets: {e}")


# Глобальный экземпляр
sheets_logger = SheetsLogger()
