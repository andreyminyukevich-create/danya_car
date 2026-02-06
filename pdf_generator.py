#!/usr/bin/env python3
"""
Генератор PDF для коммерческих предложений
С РАБОТАЮЩЕЙ кириллицей через FreeSans
"""

import os
import urllib.request
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


def download_fonts():
    """Скачивает шрифты FreeSans если их нет"""
    font_dir = "/tmp/fonts"
    os.makedirs(font_dir, exist_ok=True)
    
    fonts = {
        "FreeSans.ttf": "https://github.com/opensourcedesign/fonts/raw/master/gnu-freefont_freesans/FreeSans.ttf",
        "FreeSansBold.ttf": "https://github.com/opensourcedesign/fonts/raw/master/gnu-freefont_freesans/FreeSansBold.ttf"
    }
    
    for filename, url in fonts.items():
        filepath = os.path.join(font_dir, filename)
        if not os.path.exists(filepath):
            try:
                print(f"Downloading {filename}...")
                urllib.request.urlretrieve(url, filepath)
                print(f"Downloaded {filename}")
            except Exception as e:
                print(f"Failed to download {filename}: {e}")
    
    return font_dir


class KPPDFGenerator:
    """Генератор PDF для КП"""
    
    def __init__(self):
        self.width, self.height = A4
        self.margin = 20 * mm
        
        # Скачиваем и регистрируем шрифты
        font_dir = download_fonts()
        
        try:
            # Пробуем FreeSans (скачанный)
            pdfmetrics.registerFont(TTFont('FreeSans', os.path.join(font_dir, 'FreeSans.ttf')))
            pdfmetrics.registerFont(TTFont('FreeSansBold', os.path.join(font_dir, 'FreeSansBold.ttf')))
            self.font = 'FreeSans'
            self.font_bold = 'FreeSansBold'
            print("✅ Using FreeSans fonts")
        except Exception as e:
            print(f"Failed to load FreeSans: {e}")
            # Fallback на Helvetica (без кириллицы, но хоть что-то)
            self.font = 'Helvetica'
            self.font_bold = 'Helvetica-Bold'
            print("⚠️ Using Helvetica (no Cyrillic support)")
    
    def generate(self, car_data: dict, photo_paths: list, output_path: str):
        """Генерирует PDF файл"""
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
        c.setFont(self.font_bold, 24)
        title = car_data.get('title', 'Автомобиль')
        c.drawString(self.margin, self.height - 40*mm, title)
        
        year = car_data.get('year')
        if year:
            c.setFont(self.font, 16)
            c.drawString(self.margin, self.height - 50*mm, f"Год выпуска: {year}")
        
        c.setStrokeColor(colors.grey)
        c.setLineWidth(0.5)
        c.line(self.margin, self.height - 55*mm, self.width - self.margin, self.height - 55*mm)
    
    def _draw_photos(self, c: canvas.Canvas, photo_paths: list):
        """Рисует сетку фотографий 2x2"""
        if not photo_paths:
            return
        
        photo_width = 85 * mm
        photo_height = 64 * mm
        gap = 5 * mm
        start_x = self.margin
        start_y = self.height - 60*mm - photo_height
        
        photos_to_use = photo_paths[:4]
        
        for i, photo_path in enumerate(photos_to_use):
            row = i // 2
            col = i % 2
            
            x = start_x + col * (photo_width + gap)
            y = start_y - row * (photo_height + gap)
            
            try:
                img = Image.open(photo_path)
                
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                img.thumbnail((int(photo_width * 3), int(photo_height * 3)), Image.Resampling.LANCZOS)
                
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)
                
                c.drawImage(ImageReader(img_buffer), x, y, 
                           width=photo_width, height=photo_height,
                           preserveAspectRatio=True, anchor='c')
                
                c.setStrokeColor(colors.lightgrey)
                c.setLineWidth(0.5)
                c.rect(x, y, photo_width, photo_height)
                
            except Exception as e:
                print(f"Error loading photo {photo_path}: {e}")
                c.setFillColor(colors.lightgrey)
                c.rect(x, y, photo_width, photo_height, fill=1)
                c.setFillColor(colors.black)
                c.setFont(self.font, 10)
                c.drawCentredString(x + photo_width/2, y + photo_height/2, "Фото недоступно")
    
    def _draw_main_info(self, c: canvas.Canvas, car_data: dict):
        """Рисует основную информацию"""
        start_y = self.height - 210*mm
        
        c.setFont(self.font_bold, 14)
        c.setFillColor(colors.black)
        c.drawString(self.margin, start_y, "ОСНОВНЫЕ ХАРАКТЕРИСТИКИ")
        
        start_y -= 8*mm
        c.setFont(self.font, 11)
        
        info_items = [
            ("Двигатель:", car_data.get('engine_short', '—')),
            ("Коробка передач:", car_data.get('gearbox', '—')),
            ("Привод:", car_data.get('drive', '—')),
            ("Цвет:", car_data.get('color', '—')),
        ]
        
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
        
        # ЦЕНА
        start_y -= 5*mm
        price = car_data.get('price_rub')
        if price:
            c.setFillColor(colors.HexColor('#f0f0f0'))
            c.rect(self.margin - 3*mm, start_y - 3*mm, 
                   self.width - 2*self.margin + 6*mm, 15*mm, fill=1, stroke=0)
            
            c.setFillColor(colors.black)
            c.setFont(self.font_bold, 18)
            price_text = f"{price:,} руб.".replace(',', ' ')
            c.drawString(self.margin, start_y + 3*mm, "ЦЕНА:")
            
            c.setFillColor(colors.HexColor('#2c5aa0'))
            c.drawString(self.margin + 35*mm, start_y + 3*mm, price_text)
            
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
        
        if start_y < 50*mm:
            c.showPage()
            start_y = self.height - 40*mm
        
        c.setFont(self.font_bold, 14)
        c.setFillColor(colors.black)
        c.drawString(self.margin, start_y, "ДОПОЛНИТЕЛЬНАЯ СПЕЦИФИКАЦИЯ")
        
        start_y -= 8*mm
        
        c.setFont(self.font, 9)
        col_width = (self.width - 2 * self.margin - 5*mm) / 2
        
        for i, item in enumerate(spec_items):
            col = i % 2
            row = i // 2
            
            x = self.margin + col * (col_width + 5*mm)
            y = start_y - row * 6*mm
            
            if y < 30*mm:
                c.showPage()
                start_y = self.height - 40*mm
                y = start_y
            
            if len(item) > 40:
                item = item[:37] + '...'
            
            c.drawString(x, y, f"• {item}")
    
    def _draw_footer(self, c: canvas.Canvas):
        """Рисует футер"""
        c.setFont(self.font, 8)
        c.setFillColor(colors.grey)
        
        date_str = datetime.now().strftime("%d.%m.%Y")
        c.drawString(self.margin, 20*mm, f"Дата создания: {date_str}")
        
        c.drawRightString(self.width - self.margin, 20*mm, 
                          "Коммерческое предложение")


def generate_kp_pdf(car_data: dict, photo_paths: list, output_path: str = None) -> str:
    """Генерирует PDF файл с КП"""
    if output_path is None:
        title = car_data.get('title', 'KP').replace(' ', '_')[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/KP_{title}_{timestamp}.pdf"
    
    generator = KPPDFGenerator()
    generator.generate(car_data, photo_paths, output_path)
    
    return output_path
