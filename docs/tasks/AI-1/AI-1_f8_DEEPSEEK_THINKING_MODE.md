# DeepSeek Thinking Mode - Проблема и Решения

## Проблема

DeepSeek Chat V3 использует "thinking mode" (режим рассуждений) - перед выдачей финального ответа модель генерирует цепочку рассуждений (Chain of Thought), что улучшает точность ответов.

**Побочный эффект:** Рассуждения попадают в имена файлов, создаваемых через aider.

**Примеры неправильных имен файлов:**
```
We'll output the SEARCH/REPLACE block.strrev.py
Let's do it.factorial.py
Let's produce the SEARCH/REPLACE block.current_dt.py
Let's craft the block.sum_two_numbers.py
```

**Правильные имена:**
```
strrev.py
factorial.py
current_dt.py
sum_two_numbers.py
```

---

## Как работает Thinking Mode

### Включение Thinking Mode

DeepSeek API поддерживает два способа включения thinking mode:

**1. Использовать модель `deepseek-reasoner`:**
```python
{
    "model": "deepseek-reasoner"
}
```

**2. Установить параметр `thinking`:**
```python
{
    "model": "deepseek-chat",
    "thinking": {"type": "enabled"}
}
```

### Отключение Thinking Mode

**Параметр API:**
```python
{
    "model": "deepseek-chat",
    "thinking": {"type": "disabled"}
}
```

**Проблема:** Aider не поддерживает передачу параметра `thinking` через командную строку напрямую.

---

## Решения

### Решение 1: Пост-обработка файлов (Текущее решение) ✅

**Статус:** Реализовано в `DeepSeekProvider.post_process_files()`

**Как работает:**
1. После выполнения aider сканируются созданные файлы
2. Файлы с неправильными именами автоматически переименовываются
3. Извлекается правильное имя файла с помощью regex
4. Информация о переименовании добавляется в лог

**Преимущества:**
- ✅ Работает "из коробки"
- ✅ Не требует настройки aider
- ✅ Автоматическое исправление
- ✅ Логирование переименований

**Недостатки:**
- ❌ Файлы создаются с неправильными именами (потом исправляются)
- ❌ Не решает проблему на уровне API

**Код:**
```python
def post_process_files(self, code_dir: Path) -> List[Tuple[str, str]]:
    """Пост-обработка файлов для DeepSeek."""
    renamed_files = []
    
    for item in code_dir.iterdir():
        if is_malformed(item.name):
            correct_name = extract_correct_name(item.name)
            item.rename(code_dir / correct_name)
            renamed_files.append((item.name, correct_name))
    
    return renamed_files
```

**Примеры переименования:**
```
"We'll output the SEARCH/REPLACE block.strrev.py" → "strrev.py"
"Let's do it.factorial.py" → "factorial.py"
```

---

### Решение 2: Настройка через .aider.model.metadata.json

**Статус:** Возможно, но требует ручной настройки

**Шаги:**

**1. Создать файл `.aider.model.metadata.json` в корне проекта:**
```json
{
  "deepseek/deepseek-chat": {
    "extra_params": {
      "thinking": {
        "type": "disabled"
      }
    }
  }
}
```

**2. Aider будет использовать эти настройки при запуске**

**Преимущества:**
- ✅ Отключает thinking mode на уровне API
- ✅ Файлы создаются с правильными именами сразу

**Недостатки:**
- ❌ Требует ручного создания файла конфигурации
- ❌ Может снизить качество ответов (thinking mode улучшает точность)
- ❌ Не поддерживается официально для всех провайдеров

**Примечание:** Этот метод может не работать, так как aider использует litellm, который может не поддерживать параметр `thinking` для DeepSeek.

---

### Решение 3: Использовать reasoning_tag в aider

**Статус:** Частично применимо

Aider поддерживает настройку `reasoning_tag` для моделей, которые оборачивают рассуждения в XML теги (например, `<think>...</think>`).

**Проблема:** DeepSeek Chat V3 не использует XML теги для thinking mode при работе через API, поэтому этот метод не применим.

**Пример для DeepSeek R1 (через Fireworks):**
```yaml
- name: fireworks_ai/accounts/fireworks/models/deepseek-r1
  reasoning_tag: think
```

Aider будет отображать рассуждения, но не использовать их для инструкций по редактированию файлов.

---

### Решение 4: Использовать другую модель

**Опция 1: DeepSeek Coder**
```bash
DEEPSEEK_MODEL_NAME=deepseek/deepseek-coder
```

**Опция 2: Другие провайдеры**
```bash
CODING_LLM=ANTHROPIC
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
```

или

```bash
CODING_LLM=CHATGPT
CHATGPT_MODEL_NAME=gpt-4
```

**Преимущества:**
- ✅ Нет проблемы с thinking mode
- ✅ Файлы создаются с правильными именами

**Недостатки:**
- ❌ DeepSeek Chat V3 имеет лучшие результаты на бенчмарках aider
- ❌ Другие модели могут быть дороже

---

## Рекомендации

### Для продакшена

**Рекомендуется:** Решение 1 (Пост-обработка)

**Причины:**
1. Работает надежно и автоматически
2. Не требует дополнительной настройки
3. Сохраняет преимущества thinking mode (лучшее качество ответов)
4. Логирует все переименования для отладки

### Для экспериментов

Можно попробовать:
1. Создать `.aider.model.metadata.json` с отключением thinking mode
2. Сравнить качество ответов с/без thinking mode
3. Измерить количество ошибок в именах файлов

### Для критичных случаев

Если неправильные имена файлов недопустимы даже временно:
1. Использовать другую модель (Anthropic Claude, GPT-4)
2. Или настроить `.aider.model.metadata.json` (если работает)

---

## Техническая информация

### API DeepSeek

**Документация:** https://api-docs.deepseek.com/guides/thinking_mode

**Параметры:**
```python
{
    "model": "deepseek-chat",
    "thinking": {
        "type": "enabled" | "disabled"
    }
}
```

### Aider

**Документация:** https://aider.chat/docs/config/reasoning.html

**Поддержка reasoning:**
- ✅ Reasoning models (o1, o3, DeepSeek R1)
- ✅ Reasoning tags (`<think>...</think>`)
- ❌ Параметр `thinking` для DeepSeek Chat V3 (не поддерживается напрямую)

### Litellm

Aider использует litellm для работы с различными LLM API.

**Проблема:** litellm может не поддерживать параметр `thinking` для DeepSeek.

---

## Примеры использования

### Текущая конфигурация (с пост-обработкой)

**.env:**
```env
CODING_LLM=DEEPSEEK
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_MODEL_NAME=deepseek/deepseek-chat
```

**Запуск:**
```bash
make runagent task=TF-1 prompt="создай скрипт hello.py"
```

**Результат:**
1. Aider создает файл: `"Let's do it.hello.py"`
2. Пост-обработка переименовывает в: `"hello.py"`
3. Лог содержит информацию о переименовании

### С отключением thinking mode (экспериментально)

**.aider.model.metadata.json:**
```json
{
  "deepseek/deepseek-chat": {
    "extra_params": {
      "thinking": {
        "type": "disabled"
      }
    }
  }
}
```

**Запуск:**
```bash
make runagent task=TF-1 prompt="создай скрипт hello.py"
```

**Ожидаемый результат:**
- Файл создается сразу с правильным именем: `"hello.py"`
- Пост-обработка не требуется

**Примечание:** Этот метод может не работать. Требуется тестирование.

---

## Мониторинг и отладка

### Проверка переименований

Логи содержат секцию "Пост-обработка":

```markdown
--- Пост-обработка ---
Переименованные файлы:
  We'll output the SEARCH/REPLACE block.strrev.py -> strrev.py
```

### Статистика

Можно собирать статистику по переименованиям:
```bash
grep -r "Пост-обработка" aider/tasks/*/TF-*_log.md | wc -l
```

### Тестирование

Запустить тесты пост-обработки:
```bash
make test filter=test_providers
pytest tests/test_providers.py::TestDeepSeekProvider::test_post_process_files_malformed_filename -v
```

---

## Выводы

**Текущее решение (пост-обработка):**
- ✅ Работает надежно
- ✅ Автоматическое исправление
- ✅ Сохраняет качество ответов
- ✅ Не требует дополнительной настройки

**Альтернативы:**
- Настройка `.aider.model.metadata.json` (требует тестирования)
- Использование других моделей (снижает качество или увеличивает стоимость)

**Рекомендация:** Оставить текущее решение с пост-обработкой как основное, документировать альтернативы для экспериментов.
