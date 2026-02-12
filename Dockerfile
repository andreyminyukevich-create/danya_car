# Используем официальный Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    # Для OpenCV и EasyOCR
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    # Для компиляции
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем requirements.txt
COPY requirements.txt /app/requirements.txt

# Устанавливаем Python зависимости
# Используем --no-cache-dir для экономии места
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Копируем все файлы проекта
COPY . /app

# Создаём директорию для временных файлов
RUN mkdir -p /tmp

# Проверяем установку Tesseract
RUN tesseract --version

# Запускаем бота
CMD ["python", "bot.py"]
