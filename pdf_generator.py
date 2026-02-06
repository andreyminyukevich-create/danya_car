#!/usr/bin/env python3
"""
Генератор PDF для коммерческих предложений
С поддержкой кириллицы
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image
import io


class KPPDFGenerator:
    """Генератор PDF для КП"""
    
    def __init__(self):
        self.width, self.height = A4
        self.margin = 20 * mm
        
        # Регистрируем шрифты с поддержкой кириллицы
        try:
            # Пробуем DejaVu (обычно есть в Linux)
            pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
            self.font = 'DejaVu'
            self.font_bold = 'DejaVu-Bold'
        except:
            try:
                # Альтернатива: Liberation (тоже часто есть)
                pdfmetrics.registerFont(TTFont('Liberation', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'))
                pdfmetrics.registerFont(TTFont('Liberation-Bold', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'))
                self.font = 'Liberation'
                self.font_bold = 'Liberation-Bold'
            except:
                # Последний вариант: используем Helvetica (без кириллицы, но хоть что-то)
                self.font = 'Helvetica'
                self.font_bold = 'Helvetica-Bold'
    
    def generate(self, car_data: dict, photo_paths: list, output_path: str):
        """
        Генерирует PDF файл
        
        Args:
            car_data: Данные автомобиля
            photo_paths: Пути к фото
            output_path: Путь для сохранения PDF
        """
        c = canvas.Canvas(output_path, pagesize=A4)
        
        # Заголовок
        self._draw_header(c, car_data)
        
        # Блок с фото (сетка 2x2)
        self._draw_photos(c, photo_paths)
        
        # Основная информация
        self._draw_main_info(c, car_data)
        
        # Спецификация
        self._draw_specification(c, car_data)
        
        # Футер
        self._draw_footer(c)
        
        c.save()
        return output_path
    
    def _draw_header(self, c: canvas.Canvas, car_data: dict):
        """Рисует заголовок"""
        # Название автомобиля
        c.setFont(self.font_bold, 24)
        title = car_data.get('title', 'Автомобиль')
        c.drawString(self.margin, self.height - 40*mm, title)
        
        # Год
        year = car_data.get('year')
        if year:
            c.setFont(self.font, 16)
            c.drawString(self.margin, self.height - 50*mm, f"Год выпуска: {year}")
        
        # Линия
        c.setStrokeColor(colors.grey)
        c.setLineWidth(0.5)
        c.line(self.margin, self.height - 55*mm, self.width - self.margin, self.height - 55*mm)
    
    def _draw_photos(self, c: canvas.Canvas, photo_paths: list):
        """Рисует сетку фотографий 2x2"""
        if not photo_paths:
            return
        
        # Параметры сетки
        photo_width = 85 * mm
        photo_height = 64 * mm
        gap = 5 * mm
        start_x = self.margin
        start_y = self.height - 60*mm - photo_height
        
        # Обрезаем до 4 фото
        photos_to_use = photo_paths[:4]
        
        for i, photo_path in enumerate(photos_to_use):
            row = i // 2
            col = i % 2
            
            x = start_x + col * (photo_width + gap)
            y = start_y - row * (photo_height + gap)
            
            try:
                # Открываем и обрабатываем изображение
                img = Image.open(photo_path)
                
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Изменяем размер с сохранением пропорций
                img.thumbnail((int(photo_width * 3), int(photo_height * 3)), Image.Resampling.LANCZOS)
                
                # Сохраняем во временный буфер
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)
                
                # Рисуем на холсте
                c.drawImage(ImageReader(img_buffer), x, y, 
                           width=photo_width, height=photo_height,
                           preserveAspectRatio=True, anchor='c')
                
                # Рамка вокруг фото
                c.setStrokeColor(colors.lightgrey)
                c.setLineWidth(0.5)
                c.rect(x, y, photo_width, photo_height)
                
            except Exception as e:
                print(f"Error loading photo {photo_path}: {e}")
                # Рисуем заглушку
                c.setFillColor(colors.lightgrey)
                c.rect(x, y, photo_width, photo_height, fill=1)
                c.setFillColor(colors.black)
                c.setFont(self.font, 10)
                c.drawCentredString(x + photo_width/2, y + photo_height/2, "Фото недоступно")
    
    def _draw_main_info(self, c: canvas.Canvas, car_data: dict):
        """Рисует основную информацию"""
        start_y = self.height - 210*mm
        
        # Заголовок секции
        c.setFont(self.font_bold, 14)
        c.setFillColor(colors.black)
        c.drawString(self.margin, start_y, "ОСНОВНЫЕ ХАРАКТЕРИСТИКИ")
        
        start_y -= 8*mm
        c.setFont(self.font, 11)
        
        # Данные
        info_items = [
            ("Двигатель:", car_data.get('engine_short', '—')),
            ("Коробка передач:", car_data.get('gearbox', '—')),
            ("Привод:", car_data.get('drive', '—')),
            ("Цвет:", car_data.get('color', '—')),
        ]
        
        # Пробег
        mileage = car_data.get('mileage_km')
        if mileage is not None:
            if mileage == 0:
                info_items.append(("Пробег:", "Новый автомобиль"))
            else:
                info_items.append(("Пробег:", f"{mileage:,} км".replace(',', ' ')))
        
        for label, value in info_items:
            c.setFont(self.font_bold, 11)
            c.drawString(self.margin, start_y, label)
            c.setFont(self.font, 11)
            c.drawString(self.margin + 50*mm, start_y, str(value))
            start_y -= 6*mm
        
        # ЦЕНА (выделяем)
        start_y -= 5*mm
        price = car_data.get('price_rub')
        if price:
            # Фон для цены
            c.setFillColor(colors.HexColor('#f0f0f0'))
            c.rect(self.margin - 3*mm, start_y - 3*mm, 
                   self.width - 2*self.margin + 6*mm, 15*mm, fill=1, stroke=0)
            
            # Текст цены
            c.setFillColor(colors.black)
            c.setFont(self.font_bold, 18)
            price_text = f"{price:,} руб.".replace(',', ' ')
            c.drawString(self.margin, start_y + 3*mm, "ЦЕНА:")
            
            c.setFillColor(colors.HexColor('#2c5aa0'))
            c.drawString(self.margin + 35*mm, start_y + 3*mm, price_text)
            
            # Примечание к цене
            c.setFillColor(colors.grey)
            c.setFont(self.font, 9)
            price_note = car_data.get('price_note', 'с НДС')
            c.drawString(self.margin, start_y - 2*mm, price_note)
    
    def _draw_specification(self, c: canvas.Canvas, car_data: dict):
        """Рисует таблицу спецификации"""
        spec_items = car_data.get('spec_items', [])
        if not spec_items:
            return
        
        start_y = self.height - 265*mm
        
        # Проверяем, поместится ли на странице
        if start_y < 50*mm:
            c.showPage()  # Новая страница
            start_y = self.height - 40*mm
        
        # Заголовок
        c.setFont(self.font_bold, 14)
        c.setFillColor(colors.black)
        c.drawString(self.margin, start_y, "ДОПОЛНИТЕЛЬНАЯ СПЕЦИФИКАЦИЯ")
        
        start_y -= 8*mm
        
        # Рисуем спецификацию в 2 колонки (было 3, но кириллица шире)
        c.setFont(self.font, 9)
        col_width = (self.width - 2 * self.margin - 5*mm) / 2
        
        for i, item in enumerate(spec_items):
            col = i % 2
            row = i // 2
            
            x = self.margin + col * (col_width + 5*mm)
            y = start_y - row * 6*mm
            
            # Проверка на переполнение страницы
            if y < 30*mm:
                c.showPage()
                start_y = self.height - 40*mm
                y = start_y
            
            # Обрезаем длинные строки
            if len(item) > 40:
                item = item[:37] + '...'
            
            c.drawString(x, y, f"• {item}")
    
    def _draw_footer(self, c: canvas.Canvas):
        """Рисует футер"""
        c.setFont(self.font, 8)
        c.setFillColor(colors.grey)
        
        # Дата
        date_str = datetime.now().strftime("%d.%m.%Y")
        c.drawString(self.margin, 20*mm, f"Дата создания: {date_str}")
        
        # Контакты
        c.drawRightString(self.width - self.margin, 20*mm, 
                          "Коммерческое предложение")


def generate_kp_pdf(car_data: dict, photo_paths: list, output_path: str = None) -> str:
    """
    Генерирует PDF файл с КП
    
    Args:
        car_data: Данные автомобиля
        photo_paths: Пути к фотографиям
        output_path: Путь для сохранения (опционально)
    
    Returns:
        Путь к созданному PDF
    """
    if output_path is None:
        # Генерируем имя файла
        title = car_data.get('title', 'KP').replace(' ', '_')[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/KP_{title}_{timestamp}.pdf"
    
    generator = KPPDFGenerator()
    generator.generate(car_data, photo_paths, output_path)
    
    return output_path
