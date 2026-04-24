- [О проекте](README.md)
- [Кодинг агент](#)
- [Тесты](README.TESTS.md)
- [Интеграционные тесты](README.INTTESTS.md)

---

Содержание:
- [Кодинг агент](#кодинг-агент)
- [Установка](#установка)
- [Использование AI-агента](#использование-ai-агента)
- [Запуск через Docker](#запуск-через-docker)
- [Добавление новых LLM провайдеров](#добавление-новых-llm-провайдеров)
- [Документация](#документация)
- [Безопасность](#безопасность)

---

# Кодинг агент 

Скрипт для автономного запуска кодинг ИИ агентов: ``aider/agent.py`` в среде ``aider``.

## Установка

1. Установите зависимости:
```bash
pip install -e .
```

2. Скопируйте `.env.sample` в `.env` и заполните API ключи:
```bash
cp .env.sample .env
```

3. Отредактируйте `.env` файл, указав ваши API ключи для выбранной LLM.

## Использование AI-агента

Скрипт `aider/agent.py` позволяет автоматически выполнять задачи через AI-агента (aider).

### Примеры использования

**Создание новой задачи с промтом:**
```bash
python aider/agent.py --task="TF-2" --prompt="Напиши скрипт, выводящий в консоль 'Hello world'"
```

**Выполнение существующей задачи:**
```bash
python aider/agent.py --task="TF-1"
```

**Дополнение существующей задачи:**
```bash
python aider/agent.py --task="TF-2" --prompt="Добавь обработку исключений"
```

### Параметры

- `--task` (обязательный) - номер задачи (может содержать буквы, цифры и дефис)
- `--prompt` (необязательный) - текст задачи

### Структура файлов

- Файлы задач: `aider/tasks/<task_id>/<task_id>_task.md`
- Логи выполнения: `aider/tasks/<task_id>/<task_id>_log.md`
- Рабочая директория: `code/` (все изменения выполняются только здесь)

### Настройки LLM

В `.env` файле настройте используемую LLM:
```
CODING_LLM=DEEPSEEK
DEEPSEEK_API_KEY=sk-your-key
```

Поддерживаемые LLM: DEEPSEEK, ANTHROPIC, CHATGPT

## Запуск через Docker

Docker позволяет запускать агента без установки зависимостей локально. Все работает в изолированном контейнере.

### Предварительные требования

- Установленный Docker и Docker Compose
- Файл `.env` с настройками API ключей

### Сборка образа

```bash
docker-compose build
```

или через Makefile:

```bash
make build
```

### Запуск агента

**Создание новой задачи:**
```bash
docker-compose run --rm foundry-agent python -m agent.agent --task="TF-2" --prompt="Напиши скрипт, выводящий 'hello world' на языке python"
```

**Выполнение существующей задачи:**
```bash
docker-compose run --rm foundry-agent python -m agent.agent --task="TF-1"
```

**Через Makefile:**
```bash
make runagent task=TF-1
make runagent task=TF-2 prompt="Напиши скрипт, выводящий 'hello world' на языке python"
```

### Дополнительные команды

**Открыть shell в контейнере:**
```bash
make shell
```

**Очистить Docker ресурсы:**
```bash
make clean
```

**Показать справку:**
```bash
make help
```

### Volumes (монтируемые директории)

- `./code` → `/app/code` - рабочая директория для изменений
- `./aider/tasks` → `/app/aider/tasks` - задачи и логи
- `./.env` → `/app/.env` (read-only) - конфигурация

Все изменения, сделанные агентом в `code/` и логи в `aider/tasks/`, сохраняются на хост-машине.

## Добавление новых LLM провайдеров

Система спроектирована с использованием SOLID принципов, что позволяет легко добавлять новые LLM провайдеры.

### Шаг 1: Создать класс провайдера

Создайте файл `aider/providers/your_llm.py`:

```python
import os
from pathlib import Path
from typing import Dict, List, Tuple

from .base import BaseLLMProvider


class YourLLMProvider(BaseLLMProvider):
    """
    Провайдер для работы с YourLLM.
    
    Особенности:
    - Описание особенностей вашей LLM
    - Имя модели читается из YOUR_LLM_MODEL_NAME или используется дефолтное
    """
    
    DEFAULT_MODEL = 'your-llm/model-name'
    
    def get_model_name(self) -> str:
        """Получение названия модели из конфига или дефолтное."""
        return os.getenv('YOUR_LLM_MODEL_NAME', self.DEFAULT_MODEL)
    
    def configure_aider_command(self, base_cmd: List[str], env: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """
        Настройка команды aider для YourLLM.
        
        Args:
            base_cmd: Базовая команда aider
            env: Переменные окружения
            
        Returns:
            Кортеж (команда с параметрами, переменные окружения с API ключом)
        """
        cmd = base_cmd.copy()
        cmd.extend(['--model', self.get_model_name()])
        
        env_copy = env.copy()
        env_copy['YOUR_LLM_API_KEY'] = self.api_key
        
        return cmd, env_copy
    
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """
        Пост-обработка файлов для YourLLM.
        
        Если ваша LLM создает файлы с неправильными именами,
        реализуйте логику исправления здесь.
        
        Args:
            code_dir: Директория с кодом
            
        Returns:
            Список кортежей (старое_имя, новое_имя) переименованных файлов
        """
        # Если пост-обработка не требуется:
        return []
        
        # Или реализуйте свою логику:
        # renamed_files = []
        # ... ваша логика ...
        # return renamed_files
```

### Шаг 2: Зарегистрировать провайдер в фабрике

Обновите `aider/providers/__init__.py`:

```python
from .base import BaseLLMProvider
from .deepseek import DeepSeekProvider
from .anthropic import AnthropicProvider
from .chatgpt import ChatGPTProvider
from .your_llm import YourLLMProvider  # Добавить импорт
from .factory import LLMProviderFactory

__all__ = [
    'BaseLLMProvider',
    'DeepSeekProvider',
    'AnthropicProvider',
    'ChatGPTProvider',
    'YourLLMProvider',  # Добавить в экспорт
    'LLMProviderFactory',
]
```

Обновите `aider/providers/factory.py`:

```python
from .your_llm import YourLLMProvider  # Добавить импорт

class LLMProviderFactory:
    _providers: Dict[str, type] = {
        'DEEPSEEK': DeepSeekProvider,
        'ANTHROPIC': AnthropicProvider,
        'CHATGPT': ChatGPTProvider,
        'YOUR_LLM': YourLLMProvider,  # Добавить в словарь
    }
```

### Шаг 3: Добавить настройки в .env

Обновите `.env.sample`:

```env
# YourLLM
YOUR_LLM_API_KEY=your-api-key-here
YOUR_LLM_MODEL_NAME=your-llm/model-name
```

И добавьте в свой `.env` файл:

```env
CODING_LLM=YOUR_LLM
YOUR_LLM_API_KEY=sk-your-actual-key
YOUR_LLM_MODEL_NAME=your-llm/model-name
```

### Шаг 4: Написать тесты

Создайте тесты в `tests/test_providers.py`:

```python
class TestYourLLMProvider:
    """Тесты для YourLLMProvider."""
    
    def test_get_model_name_default(self):
        """Тест получения дефолтного названия модели."""
        with patch.dict(os.environ, {}, clear=True):
            provider = YourLLMProvider(api_key="test_key")
            assert provider.get_model_name() == 'your-llm/model-name'
    
    def test_get_model_name_from_env(self):
        """Тест получения названия модели из конфига."""
        with patch.dict(os.environ, {'YOUR_LLM_MODEL_NAME': 'custom-model'}):
            provider = YourLLMProvider(api_key="test_key")
            assert provider.get_model_name() == 'custom-model'
    
    def test_configure_aider_command(self):
        """Тест настройки команды aider."""
        provider = YourLLMProvider(api_key="test_key")
        base_cmd = ['aider', '--yes-always']
        env = {}
        
        cmd, new_env = provider.configure_aider_command(base_cmd, env)
        
        assert '--model' in cmd
        assert 'your-llm/model-name' in cmd
        assert new_env['YOUR_LLM_API_KEY'] == 'test_key'
    
    def test_post_process_files(self):
        """Тест пост-обработки файлов."""
        provider = YourLLMProvider(api_key="test_key")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = Path(tmpdir)
            renamed = provider.post_process_files(code_dir)
            assert len(renamed) == 0  # Или проверьте вашу логику
```

### Шаг 5: Запустить тесты

```bash
make test filter=test_providers.py
```

### Шаг 6: Использовать новый провайдер

```bash
# Установить в .env
CODING_LLM=YOUR_LLM

# Запустить задачу
make runagent task=TF-1
```

### Альтернативный способ: Динамическая регистрация

Если вы не хотите изменять код фабрики, можно зарегистрировать провайдер динамически:

```python
from aider.providers import LLMProviderFactory
from your_module import YourLLMProvider

# Регистрация нового провайдера
LLMProviderFactory.register_provider('YOUR_LLM', YourLLMProvider)

# Теперь можно использовать
provider = LLMProviderFactory.create_provider('YOUR_LLM', 'your-api-key')
```

### Примеры реализации

**Пример 1: Простой провайдер (как Anthropic/ChatGPT)**
- Передача API ключа через переменную окружения
- Без пост-обработки файлов
- Дефолтная модель

**Пример 2: Провайдер с пост-обработкой (как DeepSeek)**
- Передача API ключа через переменную окружения
- Пост-обработка файлов с неправильными именами
- Кастомная логика извлечения правильных имен

**Пример 3: Провайдер с особыми параметрами**
- Дополнительные параметры командной строки
- Специфичные переменные окружения
- Кастомная логика настройки

### Документация базового класса

Все провайдеры должны наследовать `BaseLLMProvider` и реализовать три метода:

```python
class BaseLLMProvider(ABC):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Получение названия модели."""
        pass
    
    @abstractmethod
    def configure_aider_command(
        self, 
        base_cmd: List[str], 
        env: Dict[str, str]
    ) -> Tuple[List[str], Dict[str, str]]:
        """Настройка команды aider и переменных окружения."""
        pass
    
    @abstractmethod
    def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
        """Пост-обработка созданных файлов."""
        pass
    
    def get_provider_name(self) -> str:
        """Получение названия провайдера."""
        return self.__class__.__name__.replace('Provider', '')
```

### Полезные ссылки

- [Документация aider](https://aider.chat/docs/)
- [Поддерживаемые модели aider](https://aider.chat/docs/llms.html)
- [Тесты провайдеров](README.TESTS.md)
- [Архитектура системы](docs/tasks/AI-1/AI-1_f8.md)

---

## Документация
Логи работы над этой задачей интеграциии ИИ агента - см. в папке `/docs/tasks/AI-1`.

---

## Безопасность

### Автоматическое подтверждение изменений

Агент использует флаг `--yes-always`, 
что означает автоматическое подтверждение всех изменений без запроса пользователя.

**Меры безопасности:**

1. **Изолированная директория:** Агент работает только в `code/`, не может изменять файлы проекта
2. **Docker изоляция:** Агент запускается в контейнере с ограниченными правами
3. **Git контроль:** Все изменения видны в `git diff` и могут быть откачены
4. **Логирование:** Все действия логируются в `agent/tasks/<task_id>/<task_id>_log.md`

**Рекомендации:**

- ✅ Проверяйте изменения через `git diff` после выполнения задачи
- ✅ Используйте git для отката нежелательных изменений
- ✅ Проверяйте логи выполнения в `agent/tasks/<task_id>/<task_id>_log.md`
- ⚠️ Не запускайте агента с непроверенными задачами на production коде
- ⚠️ Всегда проверяйте результат перед коммитом

**Откат изменений:**

```bash
# Просмотр изменений
git diff code/

# Откат всех изменений в code/
git checkout -- code/

# Откат конкретного файла
git checkout -- code/filename.py
```

### Ограничения директории кода

Агент работает только в директории, указанной в `AGENT_SOURCES_DIR` (по умолчанию `code/`).

**Относительные пути (по умолчанию):**
```env
AGENT_SOURCES_DIR=code  # Внутри проекта
AGENT_SOURCES_DIR=code/subdir  # Подкаталог
```

**Абсолютные пути (требуют явного подтверждения):**
```env
AGENT_SOURCES_DIR=/home/user/my-project/src
AGENT_ALLOW_ABSOLUTE_PATHS=true  # Обязательно!
```

**Валидация пути:**
- ❌ Абсолютные пути без подтверждения запрещены
- ❌ Выход за пределы проекта запрещен (`AGENT_SOURCES_DIR=..`)
- ❌ Защищенные системные директории запрещены
- ✅ Относительные пути внутри проекта разрешены
- ✅ Абсолютные пути с подтверждением и вне защищенных зон разрешены

**Защищенные директории (запрещены даже с подтверждением):**
- Системные: `/etc`, `/usr`, `/bin`, `/sbin`, `/boot`, `/sys`, `/proc`, `/dev`, `/var`, `/root`
- Конфиденциальные: `~/.ssh`, `~/.config`, `~/.gnupg`

**Примеры:**
```env
# ✅ Правильно
AGENT_SOURCES_DIR=code
AGENT_SOURCES_DIR=code/subdir
AGENT_SOURCES_DIR=/tmp/ai-workspace
AGENT_ALLOW_ABSOLUTE_PATHS=true

AGENT_SOURCES_DIR=/home/user/projects/my-app/src
AGENT_ALLOW_ABSOLUTE_PATHS=true

# ❌ Неправильно
AGENT_SOURCES_DIR=/etc  # Системная директория
AGENT_SOURCES_DIR=../other-project  # Выход за пределы проекта
AGENT_SOURCES_DIR=/home/user/.ssh  # Конфиденциальная директория
AGENT_SOURCES_DIR=/tmp/workspace  # Без AGENT_ALLOW_ABSOLUTE_PATHS=true
```

**Сообщения об ошибках:**

```bash
# Абсолютный путь без подтверждения
ValueError: Использование абсолютного пути требует явного подтверждения.
Путь: /home/user/my-project
Добавьте в .env: AGENT_ALLOW_ABSOLUTE_PATHS=true

# Защищенная директория
ValueError: Запрещено использовать директорию: /etc/config
Она находится в защищенной зоне: /etc
Используйте безопасную директорию (например, /tmp или ~/projects)

# Путь с '..'
ValueError: AGENT_SOURCES_DIR не должен содержать '..': ../other-project
Используйте относительный путь без '..' или абсолютный путь с AGENT_ALLOW_ABSOLUTE_PATHS=true