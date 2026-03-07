
### Инструкция по запуску
1. `py -3.11 -m venv .env` - создание окружения для python (необходима версия 3.11)
2. `.env\Scripts\activate` - активация окружения
3. `python -m pip install --upgrade pip setuptools wheel` - обновление инструментов python
4. `pip install -r requirements.txt` - установка всех необходимых библиотек
5. `python main.py` - запуск всего приложения

### Структура проекта
```python
Doc2Onto/
│
├── "README.md"                       # Этот файл
├── requirements.txt                  # Зависимости
├── "main.py"                         # Точка входа в приложение
│
├── core/                             # Ядро логики (бизнес модель системы)
│   ├── "document/"                   # Документ
│   │   ├── "document.py"             # Модель документа
│   │   └── "status.py"               # Статус обработки документа
│   ├── uddm/
│   │   ├── base.py
│   │   ├── entity.py
│   │   ├── attribute.py
│   │   ├── relation.py
│   │   ├── constraint.py
│   │   └── document.py
│   ├── rdf/
│   │   ├── triple.py
│   │   ├── graph.py
│   │   ├── validator.py
│   │   └── serializer.py
│   ├── template/
│   │   ├── base_template.py
│   │   └── template_loader.py
│   └── utils/
│       ├── text_utils.py
│       ├── extraction_helpers.py
│       └── logging.py
│
├── app/                              # Уровень приложения (контроллеры, пайплайны)
│   ├── controllers/
│   │   ├── document_controller.py
│   │   ├── template_controller.py
│   │   └── pipeline_controller.py
│   ├── pipeline/
│   │   ├── base_module.py
│   │   ├── pipeline_engine.py
│   │   ├── pipeline_registry.py
│   │   └── modules/
│   │       ├── type_classifier.py
│   │       ├── uddm_builder.py
│   │       ├── rdf_extractor.py
│   │       ├── rdf_validator.py
│   │       └── ontology_commit.py
│   └── dto/
│       └── module_result.py
│
├── ui/                               # GUI (PySide6)
│   ├── "main_window.py"              # Главное окно
│   ├── common_widgets/               # Виджеты, используемые в нескольких вкладках
│   │   └── log_viewer.py
│   └── tabs/
│       ├── documents/
│       │   ├── documents_tab.py      # Вкладка для работы с документами
│       │   ├── status_bar.py
│       │   └── uddm_editor.py
│       └── templates/
│           ├── templates_tab.py      # Вкладка для работы с шаблонами
│           └── template_editor.py
│
├── infrastructure/                   # Работа с внешними ресурсами
│   ├── storage/
│   │   ├── "document_manager.py"     # Менеджер для управления документами в системе
│   │   └── templates_manager.py      # Менеджер для управления шаблонами в системе
│   ├── ontology/
│   │   ├── ontology_repository.py
│   │   └── rdf_store_adapter.py
│   └── config/
│       └── settings.py
|
├── data/                             # Данные приложения
│   ├── "documents/"                  # Загруженные документы + промежуточные форматы и метаинформация
│   ├── templates/                    # Шаблоны (плагины)
│   └── config/                       # Конфигурация системы
│       └── settings.py               # Настройки
│
└── test/                             # Тестирование отдельных частей приложения
    ├── "documents/"                  # Тестовые документы
    └── module_tests/                 # Тесты для отдельных модулей
```

### Дополнительно
- `python.analysis.typeCheckingMode` - настройка vs code для подсветки синтаксиса
- `Ctrl + Shift + P` → `Python: Select Interpreter` - выбор нужного интерпретатора для корректной подсветки в vs code
- `Ctrl + Shift + P` → `Restart Language Server` - перезапустите Python Language Server
