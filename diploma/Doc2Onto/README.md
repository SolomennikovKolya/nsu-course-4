
### Инструкция по запуску
1. `python -m venv .env` - создание окружения для python
2. `.env\bin\activate` - активация окружения
3. `pip install -r requirements.txt` - установка всех необходимых библиотек
4. Установка сторонних зависимостей:
    - [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/)
5. `python app.py` - запуск

### Структура проекта
```
Doc2Onto/
│
├── app.py                        # Точка входа
├── requirements.txt              # Зависимости проекта (список библиотек)
├── setup.py (опц.)
│
├── config/
│   ├── settings.py
│   └── logging.conf
│
├── core/
│   ├── base_module.py            # Абстракции модулей
│   ├── exceptions.py
│   └── utils.py
│
├── modules/                      # Модули
│   ├── converter/                # Конвертер
│   │   ├── __init__.py
│   │   ├── converter.py          
│   │   └── converters/
│   │       ├── docx_to_pdf.py
│   │       ├── image_to_pdf.py
│   │       └── pdf_normalizer.py
│   │
│   ├── classifier/
│   │   └── classifier.py
│   ├── template_generator/
│   │   └── generator.py
│   ├── template_engine/
│   │   └── engine.py
│   ├── validator/
│   │   └── validator.py
│   ├── corrector/
│   │   └── corrector.py
│   ├── ner/
│   │   └── recognizer.py
│   ├── connector/
│   │   └── connector.py
│   ├── consistency_tester/
│   │   └── tester.py
│   └── audit/
│       └── auditor.py
│
├── ui/
│   ├── main_window.py            # Основное окно PyQt6
│   └── widgets/
│       └── converter_widget.py   # Пример виджета
│
└── tests/
    ├── test_converter.py
    └── test_classifier.py (будущее)
```

### Для себя
- `python.analysis.typeCheckingMode` - настройка vs code для подсветки синтаксиса
