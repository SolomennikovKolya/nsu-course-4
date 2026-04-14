
### Инструкция по запуску
1. `py -3.11 -m venv .venv` - создание окружения для python (необходима версия 3.11)
2. `.venv\Scripts\activate` - активация окружения
3. `python -m pip install --upgrade pip setuptools wheel` - обновление инструментов python
4. `pip install -r requirements.txt` - установка всех необходимых библиотек
5. `setx [variable_name] "[variable_value]"` - установка переменных среды (см. необходимые переменные в `.env.example`)
6. `python main.py` - запуск всего приложения

### Структура проекта
```python
Doc2Onto/
│
├── "README.md"                                # Этот файл
├── "requirements.txt"                         # Зависимости
├── "main.py"                                  # Точка входа
│
├── app/                                       # Уровень приложения
│   ├── "pipeline.py"                          # Пайплайн - центр управления модулями
│   ├── "context.py"                           # Контекст приложения
│   ├── "logger.py"                            # Логгер
│   └── "utils.py"                             # Утилиты
│
├── core/                                      # Ядро логики
│   ├── "document.py"                          # Модель документа
│   ├── "uddm.py"                              # Объектная модель документа в формате UDDM
│   ├── "schema.xsd"                           # Схема, описывающая структуру любого UDDM файла
│   └── "template/"
│       ├── "template.py"                      # Модель шаблона
│       ├── "base.py"                          # Контракт кода шаблона
│       ├── "field_selector.py"                # DSL описания выбора текста
│       ├── "field_extractor.py"               # DSL описания извлечения термов
│       ├── "field_validator.py"               # DSL описания валидации термов
│       └── "example.py"                       # Пример кода шаблона
│
├── modules/                                   # Модули
│   ├── "base.py"                              # Определение абстрактного BaseModule
│   ├── "converter/"                       
│   │   ├── "converter.py"                     # Конвертер
│   │   ├── "registry.py"                      # Регистр всех поддерживаемых форматов
│   │   ├── "internal/"                        # Внутренние конвертеры
│   │   ├── "external/"                        # Внешние конвертеры
│   │   ├── "nornalizers/"                     # Lossless нормализаторы форматов
│   │   └── "reverse/"                         # Конвертеры из UDDM в текстовые форматы
│   ├── "classifier.py"                        # Классификатор
│   ├── extractor.py                           # Экстрактор знаний
│   ├── validator.py                           # Валидатор
│   ├── triple_builder.py                      # Сборщик триплетов
│   └── connector.py                           # Коннектор
│
├── ui/                                        # GUI (PySide6)
│   ├── "main_window.py"                       # Главное окно
│   ├── "documents/"
│   │   ├── "documents_tab.py"                 # Вкладка для работы с документами
│   │   ├── "document_info.py"                 # Правая часть documents_tab
│   │   └── "status_progress.py"               # Виджет с прогресс баром статуса обработки документа
│   └── templates/
│       ├── "templates_tab.py"                 # Вкладка для работы с шаблонами
│       └── template_editor.py
│
├── infrastructure/                            # Работа с данными приложения
│   ├── "storage/"
│   │   ├── "base_manager.py"                  # Базовый менеджер
│   │   ├── "document_manager.py"              # Менеджер для управления документами в системе
│   │   ├── "template_manager.py"              # Менеджер для управления шаблонами в системе
│   │   └── "template_loader.py"               # Загрузчик кода шаблона 
│   └── ontology/
│       ├── ontology_repository.py
│       └── rdf_store_adapter.py
|
├── "resources/"                               # Неизменяемые ресурсы приложения
├── "data/"                                    # Динамические данные приложения
│   ├── "documents/"                           # Загруженные документы + промежуточные форматы и метаинформация
│   ├── "templates/"                           # Шаблоны (плагины)
│   └── "app.log"                              # Логи
│
└── test/
    ├── "documents/"                           # Тестовые документы
    └── module_tests/                          # Unit-тесты отдельных модулей
```

### Дополнительно
- `python.analysis.typeCheckingMode` - настройка vs code для подсветки синтаксиса
- `Ctrl + Shift + P` → `Python: Select Interpreter` - выбор нужного интерпретатора для корректной подсветки в vs code
- `Ctrl + Shift + P` → `Restart Language Server` - перезапустите Python Language Server
