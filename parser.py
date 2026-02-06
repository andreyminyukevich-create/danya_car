#!/usr/bin/env python3
"""
Парсер описаний автомобилей для КП
Заточен под копипаст с Авито (включая мусор), но старается НЕ убить полезные пункты опций.
"""

import re
from typing import Dict, Optional, List, Callable, Any


class CarDescriptionParser:
    """Парсит описание автомобиля и извлекает нужные поля"""

    def __init__(self):
        # Словари для распознавания
        self.drive_types = {
            "полный": "Полный",
            "передний": "Передний",
            "задний": "Задний",
            "4wd": "Полный",
            "awd": "Полный",
            "4matic": "Полный",
            "fwd": "Передний",
            "rwd": "Задний",
            "quattro": "Полный",
            "4x4": "Полный",
            "xdrive": "Полный",
        }

        self.gearbox_types = {
            "автомат": "Автомат",
            "механика": "Механика",
            "робот": "Робот",
            "вариатор": "Вариатор",
            "at": "Автомат",
            "amt": "Автомат",
            "mt": "Механика",
            "cvt": "Вариатор",
            "dsg": "Робот",
            "steptronic": "Автомат",
            "g-tronic": "Автомат",
            "9g-tronic": "Автомат",
        }

        self.engine_types = {
            "бензин": "Бензин",
            "дизель": "Дизель",
            "гибрид": "Гибрид",
            "электро": "Электро",
            "diesel": "Дизель",
            "petrol": "Бензин",
            "hybrid": "Гибрид",
            "electric": "Электро",
            "ev": "Электро",
        }

        self.colors = {
            "белый": "Белый",
            "черный": "Черный",
            "чёрный": "Черный",
            "серый": "Серый",
            "серебристый": "Серебристый",
            "красный": "Красный",
            "синий": "Синий",
            "зеленый": "Зеленый",
            "коричневый": "Коричневый",
            "бежевый": "Бежевый",
            "золотой": "Золотой",
            "оранжевый": "Оранжевый",
            "фиолетовый": "Фиолетовый",
        }

        # Список "мусора" из Авито
        # (важно: делаем его точнее, чтобы не вырезать опции)
        self.garbage_keywords = [
            "для бизнеса", "карьера", "каталоги", "мои объявления",
            "сообщения", "главная", "транспорт", "автомобили", "новые",
            "аватар", "расположение", "стоимость владения", "другие объявления",
            "а это наш журнал", "реклама на сайте",
            "политика конфиденциальности", "правила авито", "оферту",
            "показать карту", "изменить регион", "спросите у продавца",
            "контактное лицо", "компания", "свежие объявления", "кредит",
            "ежемесячный платёж", "автотека", "нейросеть", "оценка",
            "войти", "зарегистрироваться", "cookie",
        ]

        # Маркеры начала секций с опциями (Авито/похожие тексты)
        self.options_section_markers = [
            "опции", "дополнительные опции", "комплектация", "оснащение",
            "оборудование", "безопасность", "комфорт", "мультимедиа",
            "салон", "обзор", "помощь водителю",
        ]

    # -----------------------------
    # Public
    # -----------------------------

    def parse(self, text: str) -> Dict[str, Any]:
        """Основная функция парсинга. Возвращает словарь с извлеченными данными."""
        try:
            cleaned_text = self._clean_text(text)
            text_lower = cleaned_text.lower()

            result = {
                "title": self._safe_extract(self._extract_title, cleaned_text),
                "year": self._safe_extract(self._extract_year, cleaned_text),
                "drive": self._safe_extract(self._extract_drive, text_lower),
                "engine_short": self._safe_extract(self._extract_engine, cleaned_text),
                "gearbox": self._safe_extract(self._extract_gearbox, text_lower),
                "color": self._safe_extract(self._extract_color, text_lower),
                "mileage_km": self._safe_extract(self._extract_mileage, cleaned_text),
                "price_rub": None,              # цену просим отдельно
                "price_note": "с НДС",
                "spec_items": self._safe_extract(self._extract_spec_items, cleaned_text, default=[]),
            }

            # Добавим “насыщение” спецификации (если ещё нет)
            result["spec_items"] = self._enrich_spec_items(result, result["spec_items"])

            return result

        except Exception as e:
            print(f"Critical error in parser: {e}")
            return {
                "title": None,
                "year": None,
                "drive": None,
                "engine_short": None,
                "gearbox": None,
                "color": None,
                "mileage_km": None,
                "price_rub": None,
                "price_note": "с НДС",
                "spec_items": [],
            }

    # -----------------------------
    # Helpers
    # -----------------------------

    def _safe_extract(self, func: Callable, text: str, default=None):
        try:
            return func(text)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return default

    def _clean_text(self, text: str) -> str:
        """
        Убирает явный мусор, но НЕ вырезает строки-опции (с буллетами/тире/точками).
        """
        try:
            # нормализуем переносы
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            lines = text.split("\n")

            clean_lines: List[str] = []
            for raw in lines:
                line = raw.strip()
                if not line:
                    continue

                low = line.lower()

                # мусор по ключевикам
                if any(k in low for k in self.garbage_keywords):
                    continue

                # слишком короткие и “пустые” строки из цифр/символов
                if len(line) < 8 and re.fullmatch(r"[\d\s:—·±•\-–—]+", line):
                    continue

                # НЕ выкидываем строки только из-за буллетов/эмодзи: там часто опции
                clean_lines.append(line)

            # слегка сожмём множественные пробелы
            cleaned = "\n".join(re.sub(r"\s{2,}", " ", l) for l in clean_lines)
            return cleaned.strip()

        except Exception:
            return text

    def _dedupe_keep_order(self, items: List[str]) -> List[str]:
        seen = set()
        out = []
        for it in items:
            key = it.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it.strip())
        return out

    # -----------------------------
    # Extractors
    # -----------------------------

    def _extract_title(self, text: str) -> Optional[str]:
        """
        Извлекает название.
        Приоритет:
        1) строка вида: "BMW X6 M 4.4 AT, 2020, 50 000 км"
        2) строка "Марка Модель ..." (из известных брендов)
        3) "Модификация: ..."
        """
        # 1) заголовок с годом/пробегом
        # Пример: "Toyota Land Cruiser 4.6 AT, 2015, 182 800 км"
        m = re.search(
            r"^(.+?),\s*(19\d{2}|20[0-2]\d)\s*,\s*[\d\s]{2,}\s*км\b",
            text,
            flags=re.IGNORECASE | re.MULTILINE
        )
        if m:
            title = m.group(1).strip()
            # отрежем лишнее типа "—" в конце
            title = re.sub(r"\s*[—\-–]\s*$", "", title)
            return title[:80]

        # 2) известные бренды (расширяемость — можно добавлять)
        brands = [
            "Mercedes-Benz", "Mercedes", "Land Rover", "Range Rover",
            "BMW", "Audi", "Porsche", "Toyota", "Lexus", "Volkswagen",
            "Volvo", "Tesla", "Ford", "Chevrolet", "Nissan", "Honda",
            "Mazda", "Hyundai", "Kia", "Subaru", "Mitsubishi",
            "Jaguar", "Bentley", "Rolls-Royce", "Cadillac",
            "Lamborghini", "Ferrari", "Maserati", "Aston Martin",
            "McLaren", "Jeep", "Geely", "Zeekr", "Lynk", "Chery",
            "Haval", "Tank", "Exeed",
        ]

        for brand in brands:
            # берём 2-6 токенов после бренда до разделителей
            pattern = rf"\b{re.escape(brand)}\b\s+([A-Za-zА-Яа-я0-9\-&\. ]{{1,60}})"
            mm = re.search(pattern, text, re.IGNORECASE)
            if mm:
                chunk = (brand + " " + mm.group(1)).strip()
                chunk = re.split(r"(\n|,|Год|Пробег|Цена|Модификация:)", chunk)[0].strip()
                chunk = re.sub(r"\s{2,}", " ", chunk)
                # слишком длинное — обрежем аккуратно
                return chunk[:80]

        # 3) модификация
        mod = self._extract_modification(text)
        if mod:
            return mod[:80]

        return None

    def _extract_modification(self, text: str) -> Optional[str]:
        m = re.search(r"Модификация:\s*([^\n]+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_year(self, text: str) -> Optional[int]:
        m = re.search(r"Год\s+выпуска:\s*(\d{4})", text, re.IGNORECASE)
        if m:
            y = int(m.group(1))
            if 1980 <= y <= 2035:
                return y

        # берём самый “правдоподобный” год (не всегда max — в тексте могут быть “2024 гарантия до 2026”)
        years = [int(x) for x in re.findall(r"\b(19\d{2}|20[0-3]\d)\b", text)]
        years = [y for y in years if 1980 <= y <= 2035]
        if not years:
            return None

        # эвристика: если встречается “Год” рядом — берём его
        m2 = re.search(r"(Год|год)\D{0,20}\b(19\d{2}|20[0-3]\d)\b", text)
        if m2:
            y = int(m2.group(2))
            if 1980 <= y <= 2035:
                return y

        # иначе — чаще всего нужный самый ранний/средний? На практике у авито год один, берём max, но ограничим:
        return max(years)

    def _extract_drive(self, text_lower: str) -> Optional[str]:
        m = re.search(r"Привод:\s*([^\n]+)", text_lower)
        if m:
            drive_text = m.group(1).strip()
            for key, value in self.drive_types.items():
                if key in drive_text:
                    return value

        for key, value in self.drive_types.items():
            if re.search(rf"\b{re.escape(key)}\b", text_lower):
                return value
        return None

    def _extract_gearbox(self, text_lower: str) -> Optional[str]:
        m = re.search(r"Коробка передач:\s*([^\n]+)", text_lower)
        if m:
            gearbox_text = m.group(1).strip()
            for key, value in self.gearbox_types.items():
                if key in gearbox_text:
                    return value

        for key, value in self.gearbox_types.items():
            if re.search(rf"\b{re.escape(key)}\b", text_lower):
                return value
        return None

    def _extract_color(self, text_lower: str) -> Optional[str]:
        m = re.search(r"Цвет:\s*([^\n]+)", text_lower)
        if m:
            color_text = m.group(1).strip()
            for key, value in self.colors.items():
                if key in color_text:
                    return value

        for key, value in self.colors.items():
            if re.search(rf"\b{re.escape(key)}\b", text_lower):
                return value
        return None

    def _extract_engine(self, text: str) -> Optional[str]:
        """
        Двигатель: мощность + объем + тип.
        Понимает:
          - "585 л.с.", "249 hp"
          - "4.4 л", "2993 см3"
          - "Тип двигателя: бензин/дизель/гибрид/электро"
        """
        power = None
        volume = None
        engine_type = None

        # мощность (л.с.)
        m = re.search(r"(\d{2,4})\s*л\.?\s*с\.?", text, re.IGNORECASE)
        if m:
            power = m.group(1)

        # мощность (hp)
        if not power:
            m = re.search(r"(\d{2,4})\s*hp\b", text, re.IGNORECASE)
            if m:
                power = m.group(1)

        # объем: "4.4 л"
        m = re.search(r"(?:Объ[её]м двигателя:\s*)?([\d]+(?:[.,]\d+)?)\s*л\b", text, re.IGNORECASE)
        if m:
            volume = m.group(1).replace(",", ".")

        # объем: "2993 см3"
        if not volume:
            m = re.search(r"\b(\d{3,5})\s*(?:см3|см³|cc)\b", text, re.IGNORECASE)
            if m:
                cc = int(m.group(1))
                if 600 <= cc <= 9000:
                    volume = f"{cc/1000:.1f}".replace(".", ".")

        # тип двигателя
        low = text.lower()
        m = re.search(r"Тип двигателя:\s*([^\n]+)", low)
        if m:
            type_text = m.group(1).strip()
            for key, value in self.engine_types.items():
                if key in type_text:
                    engine_type = value
                    break
        else:
            for key, value in self.engine_types.items():
                if re.search(rf"\b{re.escape(key)}\b", low):
                    engine_type = value
                    break

        parts = []
        if power:
            parts.append(f"{power} л.с.")
        if volume:
            parts.append(f"{volume}л")
        if engine_type:
            parts.append(engine_type)

        return ", ".join(parts) if parts else None

    def _extract_mileage(self, text: str) -> Optional[int]:
        low = text.lower()

        # "новый" — риск ложных срабатываний, но ок для Авито.
        if re.search(r"\bнов(ый|ая|ое)\b", low):
            return 0

        # Пробег: 182 800 км
        m = re.search(r"Пробег:\s*([\d\s]+)\s*км", text, re.IGNORECASE)
        if m:
            s = m.group(1).replace(" ", "").replace(",", "")
            try:
                v = int(s)
                if 0 <= v <= 1_000_000:
                    return v
            except Exception:
                pass

        # В заголовке: ", 2015, 182 800 км"
        m = re.search(r",\s*(19\d{2}|20[0-2]\d)\s*,\s*([\d\s]+)\s*км", text)
        if m:
            s = m.group(2).replace(" ", "").replace(",", "")
            try:
                v = int(s)
                if 0 <= v <= 1_000_000:
                    return v
            except Exception:
                pass

        # Любое число + км (фильтр по адекватности)
        for s in re.findall(r"(\d[\d\s,]*)\s*км", low):
            s2 = s.replace(" ", "").replace(",", "")
            try:
                v = int(s2)
                if 100 <= v <= 1_000_000:
                    return v
            except Exception:
                pass

        return None

    # -----------------------------
    # Spec extraction
    # -----------------------------

    def _extract_spec_items(self, text: str) -> List[str]:
        """
        Спецификация = табличные поля + вытащенные “пункты/опции” из текста.
        """
        spec_items: List[str] = []

        # 1) табличные поля Авито
        patterns = [
            (r"Поколение:\s*([^\n]+)", "Поколение: {}"),
            (r"Модификация:\s*([^\n]+)", "Модификация: {}"),
            (r"Объ[её]м двигателя:\s*([^\n]+)", "Объём двигателя: {}"),
            (r"Тип двигателя:\s*([^\n]+)", "Тип двигателя: {}"),
            (r"Коробка передач:\s*([^\n]+)", "Коробка передач: {}"),
            (r"Привод:\s*([^\n]+)", "Привод: {}"),
            (r"Комплектация:\s*([^\n]+)", "Комплектация: {}"),
            (r"Тип кузова:\s*([^\n]+)", "Тип кузова: {}"),
            (r"Руль:\s*([^\n]+)", "Руль: {}"),
            (r"ПТС:\s*([^\n]+)", "ПТС: {}"),
            (r"Состояние:\s*([^\n]+)", "Состояние: {}"),
            (r"Количество владельцев:\s*([^\n]+)", "Владельцев: {}"),
            (r"Владельцев по ПТС:\s*([^\n]+)", "Владельцев по ПТС: {}"),
            (r"VIN:\s*([A-HJ-NPR-Z0-9]{11,20})", "VIN: {}"),
        ]
        for pattern, template in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                # чуть подчистим
                val = re.sub(r"\s{2,}", " ", val)
                spec_items.append(template.format(val))

        # 2) вытащим “опции” из маркерных строк (•, -, —, ✅)
        option_lines = self._extract_option_lines(text)
        spec_items.extend(option_lines)

        # 3) финальная чистка
        spec_items = [self._cleanup_spec_line(x) for x in spec_items]
        spec_items = [x for x in spec_items if x]

        # деды и сорт сохранением порядка
        spec_items = self._dedupe_keep_order(spec_items)

        return spec_items

    def _extract_option_lines(self, text: str) -> List[str]:
        """
        Ищем строки-опции:
        - начинаются с "•", "-", "—", "–", "✅", "▪", "◾"
        - либо находятся в секции после маркера "Опции/Комплектация/..." (эвристика)
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out: List[str] = []

        # флаг: мы внутри секции опций (после слова-маркера)
        in_options = False
        options_ttl = 0  # чтобы не утянуть половину текста

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            low = line.lower()

            # включаем режим секции опций
            if any(m in low for m in self.options_section_markers) and len(line) < 60:
                in_options = True
                options_ttl = 0
                continue

            # выключаем, если пошла явная “служебка”
            if any(k in low for k in self.garbage_keywords):
                in_options = False
                continue

            is_bullet = bool(re.match(r"^(?:[•▪◾✅\-–—]\s+)", line))
            if is_bullet:
                out.append(re.sub(r"^(?:[•▪◾✅\-–—]\s+)", "", line).strip())
                continue

            # если в секции опций — берем похожие строки
            if in_options:
                # ограничим по количеству строк, чтобы не перетащить описание продавца
                options_ttl += 1
                if options_ttl > 60:
                    in_options = False
                    continue

                # фильтруем: слишком длинные “простыни” — не берем
                if len(line) > 90:
                    continue

                # исключаем строки вида "Все характеристики", "Описание" и т.п.
                if any(w in low for w in ["описание", "все характеристики", "показать", "читать полностью"]):
                    continue

                # если похоже на пункт (есть запятая/слово и нет точки в конце)
                if re.search(r"[А-Яа-яA-Za-z0-9]", line):
                    out.append(line)

        return out

    def _cleanup_spec_line(self, s: str) -> str:
        s = s.strip()
        s = re.sub(r"\s{2,}", " ", s)

        # выкинуть совсем короткое
        if len(s) < 3:
            return ""

        # выкинуть служебные хвосты
        bad = ["авито", "поделиться", "пожаловаться", "показать", "читать полностью"]
        low = s.lower()
        if any(b in low for b in bad):
            return ""

        # не таскаем “цена/кредит/платёж”
        if any(b in low for b in ["кредит", "платеж", "платёж", "₽", "руб"]):
            return ""

        # точка в конце — ок, но уберем лишние
        s = s.strip(" •-–—\t")

        return s

    def _enrich_spec_items(self, parsed: Dict[str, Any], spec: List[str]) -> List[str]:
        """
        Добавляет ключевые поля в спецификацию (чтобы КП выглядело полнее),
        но не дублирует если они уже есть.
        """
        extra = []
        if parsed.get("drive"):
            extra.append(f"Привод: {parsed['drive']}")
        if parsed.get("gearbox"):
            extra.append(f"Коробка передач: {parsed['gearbox']}")
        if parsed.get("engine_short"):
            extra.append(f"Двигатель: {parsed['engine_short']}")
        if parsed.get("color"):
            extra.append(f"Цвет: {parsed['color']}")

        all_items = spec + extra
        all_items = [x for x in all_items if x]
        return self._dedupe_keep_order(all_items)
