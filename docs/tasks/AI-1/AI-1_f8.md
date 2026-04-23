# AI-1_f8: Рефакторинг agent.py согласно SOLID принципам

**Дата:** 23.04.2026 18:30

**Задача:** Рефакторинг кода в `aider/agent.py` с использованием классов и принципов SOLID.

---

**Проблема:**

Исходный код в `agent.py` был монолитным:
- Все функции в одном файле
- Нет разделения ответственности
- Сложно добавлять новые LLM провайдеры
- Пост-обработка была жестко привязана к DeepSeek
- Нет тестов

---

**Решение:**

Создана новая архитектура с разделением ответственности согласно SOLID:

**1. Провайдеры LLM (`aider/providers/`)**

**Базовый класс `BaseLLMProvider`:**
```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def get_model_name(self) -> str:
        pass
    
    @abstractmethod
    def configure_aider_command(self, base_cmd, env):
        pass
    
    @abstractmethod
    def post_process_files(self, code_dir):
        pass
```

**Реализации:**
- `DeepSeekProvider` - с пост-обработкой файлов
- `AnthropicProvider` - без пост-обработки
- `ChatGPTProvider` - без пост-обработки

**2. Фабрика `LLMProviderFactory`:**

```python
class LLMProviderFactory:
    @classmethod
    def create_from_env(cls) -> BaseLLMProvider:
        # Создает провайдер из переменных окружения
        pass
    
    @classmethod
    def register_provider(cls, llm_type, provider_class):
        # Регистрация нового провайдера
        pass
```

**3. Менеджеры (`aider/core/`)**

**TaskManager:**
- Валидация номеров задач
- Загрузка/создание задач
- Получение путей к файлам

**LogManager:**
- Сохранение логов
- Форматирование информации о пост-обработке

**AiderRunner:**
- Запуск aider с провайдером
- Обработка результатов

---

**Структура проекта:**

```
aider/
├── agent.py                    # Точка входа
├── providers/                  # Провайдеры LLM
│   ├── __init__.py
│   ├── base.py                # Базовый класс
│   ├── deepseek.py            # DeepSeek провайдер
│   ├── anthropic.py           # Anthropic провайдер
│   ├── chatgpt.py             # ChatGPT провайдер
│   └── factory.py             # Фабрика провайдеров
└── core/                       # Основная логика
    ├── __init__.py
    ├── task_manager.py        # Менеджер задач
    ├── log_manager.py         # Менеджер логов
    └── aider_runner.py        # Запуск aider

tests/                          # Тесты
├── __init__.py
├── conftest.py
├── test_providers.py          # Тесты провайдеров
└── test_core.py               # Тесты core модулей
```

---

**Преимущества новой архитектуры:**

**1. Single Responsibility Principle (SRP):**
- Каждый класс отвечает за одну задачу
- `TaskManager` - только задачи
- `LogManager` - только логи
- `AiderRunner` - только запуск aider

**2. Open/Closed Principle (OCP):**
- Легко добавить новый провайдер без изменения существующего кода
- Достаточно создать класс, наследующий `BaseLLMProvider`

**3. Liskov Substitution Principle (LSP):**
- Все провайдеры взаимозаменяемы
- Можно использовать любой провайдер через базовый интерфейс

**4. Interface Segregation Principle (ISP):**
- Интерфейс `BaseLLMProvider` минимален
- Каждый метод необходим

**5. Dependency Inversion Principle (DIP):**
- `AiderRunner` зависит от абстракции `BaseLLMProvider`
- Не зависит от конкретных реализаций

---

**Пост-обработка для каждого провайдера:**

**DeepSeek:**
```python
def post_process_files(self, code_dir):
    # Исправление имен файлов с рассуждениями
    # "Let's do it.factorial.py" -> "factorial.py"
    return renamed_files
```

**Anthropic/ChatGPT:**
```python
def post_process_files(self, code_dir):
    # Пока не требуется
    return []
```

---

**Добавление нового провайдера:**

```python
# 1. Создать класс провайдера
class GeminiProvider(BaseLLMProvider):
    def get_model_name(self):
        return 'gemini-pro'
    
    def configure_aider_command(self, base_cmd, env):
        # Настройка команды
        pass
    
    def post_process_files(self, code_dir):
        # Пост-обработка (если нужна)
        return []

# 2. Зарегистрировать в фабрике
LLMProviderFactory.register_provider('GEMINI', GeminiProvider)

# 3. Добавить в .env
CODING_LLM=GEMINI
GEMINI_API_KEY=your_key
```

---

**Тесты:**

Созданы тесты для всех классов:

**test_providers.py:**
- Тесты для каждого провайдера
- Тесты фабрики
- Тесты пост-обработки

**test_core.py:**
- Тесты TaskManager
- Тесты LogManager

**Запуск тестов:**
```bash
pytest tests/
```

---

**Использование:**

```bash
# Запуск с DeepSeek (по умолчанию)
make runagent task=TF-1

# Запуск с Anthropic
CODING_LLM=ANTHROPIC make runagent task=TF-1

# Запуск с ChatGPT
CODING_LLM=CHATGPT make runagent task=TF-1
```

**Вывод:**
```
Выполнение задачи TF-1...
Используется провайдер: DeepSeek
Модель: deepseek/deepseek-chat
Задача выполнена, лог работ сохранен в файл: ...
```

---

**Комментарий для коммита:**

```
AI-1_f8: Рефакторинг agent.py согласно SOLID принципам

Проблема:
- Монолитный код в одном файле
- Нет разделения ответственности
- Сложно добавлять новые LLM
- Пост-обработка жестко привязана к DeepSeek
- Нет тестов

Решение:
- Создана иерархия классов провайдеров LLM
- Базовый класс BaseLLMProvider с абстрактными методами
- Реализации для DeepSeek, Anthropic, ChatGPT
- Фабрика LLMProviderFactory для создания провайдеров
- Менеджеры TaskManager, LogManager, AiderRunner
- Каждый провайдер имеет свою пост-обработку
- Написаны тесты для всех классов

Архитектура:
- SRP: каждый класс отвечает за одну задачу
- OCP: легко добавить новый провайдер
- LSP: все провайдеры взаимозаменяемы
- ISP: минимальный интерфейс
- DIP: зависимость от абстракций

Файлы:
- aider/providers/ - провайдеры LLM
- aider/core/ - основная логика
- tests/ - тесты
- agent.py - точка входа (упрощен)

Преимущества:
- Легко добавлять новые LLM
- Каждый провайдер имеет свою пост-обработку
- Код покрыт тестами
- Чистая архитектура
```

---

**Инструкции по тестированию:**

```bash
# 1. Запустить тесты
pytest tests/ -v

# 2. Проверить работу с DeepSeek
make runagent task=TF-6 prompt="напиши скрипт hello world"

# 3. Проверить пост-обработку
ls code/
# Должен быть файл с правильным именем (hello_world.py или similar)

# 4. Проверить лог
cat aider/tasks/TF-6/TF-6_log.md
# Должна быть секция "Пост-обработка" если были переименования

# 5. Проверить вывод провайдера
# Должно быть:
# "Используется провайдер: DeepSeek"
# "Модель: deepseek/deepseek-chat"
```

**Ожидаемый результат:**
- Все тесты проходят ✅
- Провайдер создается корректно ✅
- Пост-обработка работает для DeepSeek ✅
- Код чистый и расширяемый ✅
