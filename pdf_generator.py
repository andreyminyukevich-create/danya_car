#!/usr/bin/env python3
"""
PDF генератор КП (премиум-шаблон, стабильная верстка без наложений)

Формат как в твоих примерах:
- Стр.1: верхняя шапка (имя пользователя), заголовок авто, HERO-блок (серый фон: слева краткие характеристики, справа 1 фото),
         ниже сетка доп. фото, ниже спецификация (3 колонки), внизу плашка цены.
- Стр.2+ (если много спецификации): продолжение спецификации, футер на каждой странице.
- Фото: EXIF-поворот, "cover" кадрирование (нормально для вертикальных), скругление углов (PNG alpha).
- Спецификация: нормализация (если прилетает строка с • / ; / переносами), перенос по ширине, раскладка в 3 колонки без наложений.

Зависимости:
  pip install reportlab pillow

Как использовать:
  from pdf_generator import generate_kp_pdf
  pdf_path = generate_kp_pdf(car_data, photo_paths)

Ожидаемые ключи car_data:
  title, year, drive, engine_short, gearbox, color, mileage_km,
  price_rub, price_note, spec_items,
  user_name (имя для шапки), kp_number (необязательно)
"""

import os
import io
import urllib.request
from datetime import datetime
from typing import List, Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from PIL import Image, ImageOps, ImageDraw


# -----------------------------
# Fonts
# -----------------------------

def download_fonts() -> str:
    """Скачивает FreeSans шрифты (кириллица) если их нет."""
    font_dir = "/tmp/fonts"
    os.makedirs(font_dir, exist_ok=True)

    fonts = {
        "FreeSans.ttf": "https://github.com/opensourcedesign/fonts/raw/master/gnu-freefont_freesans/FreeSans.ttf",
        "FreeSansBold.ttf": "https://github.com/opensourcedesign/fonts/raw/master/gnu-freefont_freesans/FreeSansBold.ttf",
    }

    for filename, url in fonts.items():
        filepath = os.path.join(font_dir, filename)
        if not os.path.exists(filepath):
            try:
                urllib.request.urlretrieve(url, filepath)
            except Exception as e:
                print(f"Failed to download {filename}: {e}")

    return font_dir


# -----------------------------
# Generator
# -----------------------------

class KPPDFGenerator:
    def __init__(self):
        self.width, self.height = A4
        self.margin = 18 * mm

        self.top_y = self.height - 16 * mm
        self.footer_y = 12 * mm

        # reserved bottoms
        self.bottom_default = 22 * mm  # футер + безопасный низ
        self.pricebar_height = 16 * mm
        self.pricebar_gap = 6 * mm
        self.bottom_with_price = self.footer_y + self.pricebar_height + self.pricebar_gap + 6 * mm

        self.page_num = 1
        self.price_drawn_on_first_page = False

        font_dir = download_fonts()
        try:
            pdfmetrics.registerFont(TTFont("FreeSans", os.path.join(font_dir, "FreeSans.ttf")))
            pdfmetrics.registerFont(TTFont("FreeSansBold", os.path.join(font_dir, "FreeSansBold.ttf")))
            self.font = "FreeSans"
            self.font_bold = "FreeSansBold"
            print("✅ Using FreeSans fonts")
        except Exception as e:
            print(f"⚠️ Failed to load FreeSans: {e}")
            self.font = "Helvetica"
            self.font_bold = "Helvetica-Bold"
            print("⚠️ Using Helvetica (no Cyrillic support)")

        # palette
        self.c_title = colors.HexColor("#0f172a")
        self.c_accent = colors.HexColor("#2c5aa0")
        self.c_grey_bg = colors.HexColor("#f3f4f6")
        self.c_grey_text = colors.HexColor("#6b7280")
        self.c_divider = colors.HexColor("#e5e7eb")

        # legal footer text
        self.legal_text = (
            "Остальные фото — по запросу. Комплектацию уточняйте у менеджера. "
            "Предложение действительно в течение 3 дней."
        )

    # -----------------------------
    # Public
    # -----------------------------

    def generate(self, car_data: dict, photo_paths: List[str], output_path: str) -> str:
        c = canvas.Canvas(output_path, pagesize=A4)

        self.page_num = 1
        self.price_drawn_on_first_page = False

        price_text, price_note = self._format_price(car_data.get("price_rub"), car_data.get("price_note"))
        reserve_price = bool(price_text)

        # Header line (name + kp number/date)
        y = self._draw_top_header(c, car_data)
        y -= 6 * mm

        # Car title
        y = self._draw_car_title(c, car_data, y, reserve_price_on_first_page=reserve_price)
        y -= 4 * mm

        photos = [p for p in (photo_paths or []) if p]
        hero_photo = photos[0] if photos else None
        other_photos = photos[1:] if len(photos) > 1 else []

        # Hero block
        y = self._draw_hero_block(c, car_data, hero_photo, y, reserve_price_on_first_page=reserve_price)
        y -= 7 * mm

        # Optional photos grid (below hero)
        y = self._draw_photos_grid(c, car_data, other_photos, y, reserve_price_on_first_page=reserve_price)
        if other_photos:
            y -= 6 * mm

        # Specification (3 columns), may continue on next pages
        y = self._draw_specification_3col(
            c,
            car_data,
            y,
            reserve_price_on_first_page=reserve_price
        )

        # Price bar fixed at bottom of first page
        if price_text:
            self._draw_price_bar(c, price_text, price_note)
            self.price_drawn_on_first_page = True

        # Footer on last page
        self._draw_footer(c)

        c.save()
        return output_path

    # -----------------------------
    # Page helpers
    # -----------------------------

    def _current_bottom_limit(self, reserve_price_on_first_page: bool) -> float:
        if self.page_num == 1 and reserve_price_on_first_page and not self.price_drawn_on_first_page:
            return self.bottom_with_price
        return self.bottom_default

    def _new_page(self, c: canvas.Canvas, car_data: dict):
        self._draw_footer(c)
        c.showPage()
        self.page_num += 1

        # repeat top header on each page
        self._draw_top_header(c, car_data)

    def _ensure_space(self, c: canvas.Canvas, car_data: dict, y: float, needed: float, reserve_price_on_first_page: bool) -> float:
        bottom = self._current_bottom_limit(reserve_price_on_first_page)
        if y - needed < bottom:
            self._new_page(c, car_data)
            return self.top_y - 12 * mm  # after header
        return y

    # -----------------------------
    # Text / formatting
    # -----------------------------

    def _text_width(self, text: str, font_name: str, font_size: int) -> float:
        return pdfmetrics.stringWidth(text, font_name, font_size)

    def _wrap_text(self, text: str, font_name: str, font_size: int, max_width: float) -> List[str]:
        if not text:
            return []
        words = str(text).split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if self._text_width(test, font_name, font_size) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _format_mileage(self, mileage_km) -> str:
        if mileage_km is None or str(mileage_km).strip() == "":
            return "—"
        try:
            m = int(mileage_km)
            if m == 0:
                return "Новый автомобиль"
            return f"{m:,} км".replace(",", " ")
        except Exception:
            return str(mileage_km)

    def _format_price(self, price_rub, price_note) -> Tuple[Optional[str], str]:
        if price_rub is None or str(price_rub).strip() == "":
            return None, str(price_note or "")
        note = str(price_note or "с НДС").strip()
        try:
            p = int(str(price_rub).replace(" ", "").replace("₽", "").replace("руб.", "").replace("руб", "").strip())
            return f"{p:,} руб.".replace(",", " "), note
        except Exception:
            return str(price_rub).strip(), note

    def _normalize_spec_items(self, spec_items) -> List[str]:
        if not spec_items:
            return []
        out: List[str] = []
        for item in spec_items:
            if not item:
                continue
            s = str(item).strip()
            if not s:
                continue
            if "•" in s:
                out.extend([p.strip() for p in s.split("•") if p.strip()])
            elif "\n" in s:
                out.extend([p.strip() for p in s.splitlines() if p.strip()])
            elif ";" in s:
                out.extend([p.strip() for p in s.split(";") if p.strip()])
            else:
                out.append(s)
        return [x for x in out if x]

    # -----------------------------
    # Image processing (EXIF, cover, rounded)
    # -----------------------------

    def _prepare_image_bytes_cover_rounded(
        self,
        path: str,
        target_w_pt: float,
        target_h_pt: float,
        radius_pt: float = 10.0
    ) -> Optional[io.BytesIO]:
        """
        Готовит PNG с альфой:
        - учитывает EXIF ориентацию
        - режет под нужное соотношение сторон (cover)
        - ресайз
        - скругляет углы
        """
        if not path:
            return None

        # 1pt -> ~2.6px (компромисс качество/вес)
        scale = 2.6
        tw = max(1, int(target_w_pt * scale))
        th = max(1, int(target_h_pt * scale))
        r = max(0, int(radius_pt * scale))

        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img)  # фото с телефона
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")

            # cover crop
            iw, ih = img.size
            target_ratio = tw / th
            src_ratio = iw / ih

            if src_ratio > target_ratio:
                # шире — режем ширину
                new_w = int(ih * target_ratio)
                left = (iw - new_w) // 2
                img = img.crop((left, 0, left + new_w, ih))
            else:
                # выше — режем высоту
                new_h = int(iw / target_ratio)
                top = (ih - new_h) // 2
                img = img.crop((0, top, iw, top + new_h))

            img = img.resize((tw, th), Image.Resampling.LANCZOS)

            # rounded corners
            if r > 0:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                mask = Image.new("L", (tw, th), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, tw, th), radius=r, fill=255)
                img.putalpha(mask)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            return buf

        except Exception as e:
            print(f"Image prepare error {path}: {e}")
            return None

    def _draw_image_frame(self, c: canvas.Canvas, img_path: str, x: float, y: float, w: float, h: float, radius: float = 10.0):
        buf = self._prepare_image_bytes_cover_rounded(img_path, w, h, radius_pt=radius)
        if buf:
            c.drawImage(ImageReader(buf), x, y, width=w, height=h, mask="auto")
        else:
            c.setFillColor(colors.lightgrey)
            c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.setFont(self.font, 10)
            c.drawCentredString(x + w / 2, y + h / 2, "Фото недоступно")

    # -----------------------------
    # Blocks
    # -----------------------------

    def _draw_top_header(self, c: canvas.Canvas, car_data: dict) -> float:
        """
        Верхняя строка:
        - слева: имя пользователя (только имя)
        - справа: номер КП + дата
        """
        user_name = str(car_data.get("user_name") or "Менеджер").strip()
        date_str = datetime.now().strftime("%d.%m.%Y")

        kp_num = car_data.get("kp_number")
        if not kp_num:
            kp_num = datetime.now().strftime("KP-%Y%m%d-%H%M%S")

        y = self.top_y

        c.setFont(self.font, 9)
        c.setFillColor(self.c_grey_text)
        c.drawString(self.margin, y, user_name)

        c.drawRightString(self.width - self.margin, y, f"{kp_num} • {date_str}")

        # divider
        c.setStrokeColor(self.c_divider)
        c.setLineWidth(0.7)
        c.line(self.margin, y - 4.5 * mm, self.width - self.margin, y - 4.5 * mm)

        return y - 8 * mm

    def _draw_car_title(self, c: canvas.Canvas, car_data: dict, y: float, reserve_price_on_first_page: bool) -> float:
        title = str(car_data.get("title") or "Автомобиль").strip()
        max_w = self.width - 2 * self.margin

        c.setFillColor(self.c_title)
        c.setFont(self.font_bold, 22)

        lines = self._wrap_text(title, self.font_bold, 22, max_w)
        lines = lines[:2] if lines else [title]

        needed = len(lines) * 10.5 * mm + 5 * mm
        y = self._ensure_space(c, car_data, y, needed, reserve_price_on_first_page)

        for ln in lines:
            c.drawString(self.margin, y, ln)
            y -= 10.5 * mm

        c.setFont(self.font, 11)
        c.setFillColor(self.c_grey_text)
        c.drawString(self.margin, y + 2 * mm, "Коммерческое предложение")
        y -= 2 * mm

        return y

    def _draw_hero_block(self, c: canvas.Canvas, car_data: dict, hero_photo: Optional[str], y: float, reserve_price_on_first_page: bool) -> float:
        """
        Серый блок:
        - слева: краткие характеристики
        - справа: hero фото
        """
        block_h = 68 * mm
        y = self._ensure_space(c, car_data, y, block_h, reserve_price_on_first_page)

        x0 = self.margin
        y0 = y - block_h
        w0 = self.width - 2 * self.margin

        c.setFillColor(self.c_grey_bg)
        c.roundRect(x0, y0, w0, block_h, 8, fill=1, stroke=0)

        left_w = w0 * 0.44
        pad = 6 * mm

        photo_x = x0 + left_w + pad
        photo_w = w0 - left_w - 2 * pad
        photo_h = block_h - 2 * pad
        photo_y = y0 + pad

        if hero_photo:
            self._draw_image_frame(c, hero_photo, photo_x, photo_y, photo_w, photo_h, radius=8.0)
        else:
            c.setFillColor(colors.HexColor("#e5e7eb"))
            c.roundRect(photo_x, photo_y, photo_w, photo_h, 8, fill=1, stroke=0)

        # short specs
        year = car_data.get("year", "—")
        drive = car_data.get("drive", "—")
        engine = car_data.get("engine_short", "—")
        gearbox = car_data.get("gearbox", "—")
        color_ = car_data.get("color", "—")
        mileage = self._format_mileage(car_data.get("mileage_km"))

        items = [
            ("Год выпуска", year),
            ("Привод", drive),
            ("Двигатель", engine),
            ("Коробка", gearbox),
            ("Цвет", color_),
            ("Пробег", mileage),
        ]

        tx = x0 + pad
        c.setFillColor(self.c_title)
        c.setFont(self.font_bold, 12)
        c.drawString(tx, y0 + block_h - 10 * mm, "Кратко")

        max_val_w = left_w - 2 * pad
        line_h = 8.0 * mm
        cur_y = y0 + block_h - 18 * mm

        for label, value in items:
            c.setFont(self.font, 8)
            c.setFillColor(self.c_grey_text)
            c.drawString(tx, cur_y, f"{label}")

            c.setFont(self.font_bold, 10)
            c.setFillColor(colors.HexColor("#374151"))

            v_lines = self._wrap_text(str(value or "—"), self.font_bold, 10, max_val_w)
            v_lines = v_lines[:2] if v_lines else ["—"]

            v_y = cur_y - 4.2 * mm
            for ln in v_lines:
                c.drawString(tx, v_y, ln)
                v_y -= 4.8 * mm

            cur_y -= line_h

        return y0

    def _draw_photos_grid(self, c: canvas.Canvas, car_data: dict, photo_paths: List[str], y: float, reserve_price_on_first_page: bool) -> float:
        """
        Доп. фото под hero:
        - максимум 6 фото
        - grid 3 колонки (2 ряда), адаптивно
        - если не влазит на 1 стр. (с учетом плашки цены) — переносим на след. страницу
        """
        photos = [p for p in (photo_paths or []) if p][:6]
        if not photos:
            return y

        cols = 3 if len(photos) >= 3 else 2
        gap = 4 * mm

        grid_w = self.width - 2 * self.margin
        cell_w = (grid_w - (cols - 1) * gap) / cols
        cell_h = 36 * mm
        radius = 7.0

        rows = (len(photos) + cols - 1) // cols
        rows = min(rows, 2)

        needed_h = rows * cell_h + (rows - 1) * gap

        # если не хватает места — делаем новую страницу (в отличие от старой версии)
        y = self._ensure_space(c, car_data, y, needed_h, reserve_price_on_first_page)

        idx = 0
        start_y = y
        for r in range(rows):
            row_top = start_y - r * (cell_h + gap)
            for col in range(cols):
                if idx >= len(photos):
                    break
                x = self.margin + col * (cell_w + gap)
                y0 = row_top - cell_h
                self._draw_image_frame(c, photos[idx], x, y0, cell_w, cell_h, radius=radius)
                idx += 1

        return start_y - needed_h

    def _draw_specification_3col(self, c: canvas.Canvas, car_data: dict, y: float, reserve_price_on_first_page: bool) -> float:
        spec_items = self._normalize_spec_items(car_data.get("spec_items", []))
        if not spec_items:
            return y

        # title
        title_h = 10 * mm
        y = self._ensure_space(c, car_data, y, title_h, reserve_price_on_first_page)

        c.setFont(self.font_bold, 13)
        c.setFillColor(self.c_title)
        c.drawString(self.margin, y, "Спецификация")
        y -= 7 * mm

        cols = 3
        gap = 5 * mm
        usable_w = self.width - 2 * self.margin
        col_w = (usable_w - (cols - 1) * gap) / cols

        font_size = 9
        line_h = 4.6 * mm
        c.setFont(self.font, font_size)
        c.setFillColor(colors.black)

        # masonry columns: keep current y per column, always place to the highest column
        col_y = [y, y, y]

        def place_in_column(col_idx: int, lines: List[str]) -> None:
            nonlocal col_y
            x = self.margin + col_idx * (col_w + gap)
            yy = col_y[col_idx]
            for ln in lines:
                c.drawString(x, yy, ln)
                yy -= line_h
            col_y[col_idx] = yy - 1.2 * mm

        for item in spec_items:
            text = f"• {item}"
            lines = self._wrap_text(text, self.font, font_size, col_w)
            if not lines:
                lines = [text]

            needed = (len(lines) * line_h) + 2.5 * mm

            # pick highest column
            col_idx = max(range(cols), key=lambda i: col_y[i])

            bottom = self._current_bottom_limit(reserve_price_on_first_page)
            if col_y[col_idx] - needed < bottom:
                # new page
                self._new_page(c, car_data)

                # after new page, no price reserve (price bar only on first page)
                reserve_price_on_first_page = False

                y = self.top_y - 12 * mm
                c.setFont(self.font_bold, 13)
                c.setFillColor(self.c_title)
                c.drawString(self.margin, y, "Спецификация (продолжение)")
                y -= 7 * mm

                c.setFont(self.font, font_size)
                c.setFillColor(colors.black)
                col_y = [y, y, y]

                # recompute bottom for subsequent pages
                bottom = self._current_bottom_limit(reserve_price_on_first_page)

            place_in_column(col_idx, lines)

        return min(col_y)

    def _draw_price_bar(self, c: canvas.Canvas, price_text: str, price_note: str):
        """Плашка цены фиксировано на 1 странице."""
        y0 = self.footer_y + 8 * mm
        x0 = self.margin
        w0 = self.width - 2 * self.margin
        h0 = self.pricebar_height

        c.setFillColor(self.c_grey_bg)
        c.roundRect(x0, y0, w0, h0, 8, fill=1, stroke=0)

        c.setFont(self.font_bold, 14)
        c.setFillColor(self.c_title)
        c.drawString(x0 + 6 * mm, y0 + 6.2 * mm, "Стоимость:")

        c.setFont(self.font_bold, 15)
        c.setFillColor(self.c_accent)
        c.drawString(x0 + 40 * mm, y0 + 6.0 * mm, price_text)

        note = (price_note or "").strip()
        if note:
            c.setFont(self.font, 9)
            c.setFillColor(self.c_grey_text)
            c.drawRightString(x0 + w0 - 6 * mm, y0 + 6.5 * mm, note)

    def _draw_footer(self, c: canvas.Canvas):
        """Футер на каждой странице."""
        date_str = datetime.now().strftime("%d.%m.%Y")

        c.setFont(self.font, 7.8)
        c.setFillColor(self.c_grey_text)
        c.drawCentredString(self.width / 2, self.footer_y + 6 * mm, self.legal_text)

        c.setFont(self.font, 8)
        c.drawString(self.margin, self.footer_y, f"Дата создания: {date_str}")
        c.drawRightString(self.width - self.margin, self.footer_y, "Коммерческое предложение")


# -----------------------------
# Convenience function
# -----------------------------

def generate_kp_pdf(car_data: dict, photo_paths: list, output_path: str = None) -> str:
    if output_path is None:
        title = car_data.get("title", "KP")
        safe = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in str(title))
        safe = safe[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/KP_{safe}_{timestamp}.pdf"

    gen = KPPDFGenerator()
    gen.generate(car_data, photo_paths, output_path)
    return output_path
