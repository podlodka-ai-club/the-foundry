.PHONY: build runagent shell clean test test-unit test-int help

help:
	@echo "Доступные команды:"
	@echo "  make build                         - Собрать Docker образ"
	@echo "  make runagent task=XX              - Запустить агента для выполнения задачи из файла agent/tasks/XX/XX_task.md"
	@echo "  make runagent task=XX prompt=\"YY\"  - Запустить агента для создания задачи XX из промта YY"
	@echo "  make test                          - Запустить все тесты (unit + integration)"
	@echo "  make test-unit                     - Запустить только unit тесты (быстрые)"
	@echo "  make test-int                      - Запустить только интеграционные тесты (медленные, требуют LLM API)"
	@echo "  make test filter=test_name         - Запустить конкретный тест"
	@echo "  make shell                         - Открыть shell в контейнере"
	@echo "  make clean                         - Очистить Docker ресурсы"
	@echo ""
	@echo "Примеры:"
	@echo "  make runagent task=TF-1"
	@echo "  make runagent task=TF-2 prompt=\"Создай скрипт на python - выводящий на экран 'hello world'\""
	@echo "  make test"
	@echo "  make test-unit"
	@echo "  make test-int"
	@echo "  make test filter=test_providers.py"
	@echo "  make test filter=test_core"

# Собрать Docker образ
build:
	docker-compose build

# Запустить агента для выполнения задачи из файла
runagent:
ifdef prompt
	docker-compose run --rm foundry-agent python -m agent.agent --task="$(task)" --prompt="$(prompt)"
else
	docker-compose run --rm foundry-agent python -m agent.agent --task="$(task)"
endif

# Запустить все тесты (unit + integration)
test:
ifdef filter
	@if echo "$(filter)" | grep -q "\.py$$"; then \
		pytest tests/$(filter) -v; \
	else \
		pytest tests/$(filter).py -v; \
	fi
else
	pytest tests/ -v
endif

# Запустить только unit тесты (быстрые)
test-unit:
	pytest tests/ -v -m "not integration"

# Запустить только интеграционные тесты
test-int:
	pytest tests/ -v -m integration

# Открыть shell в контейнере
shell:
	docker-compose run --rm foundry-agent /bin/bash

# Scoped cleanup
# ✅ Останавливает и удаляет контейнеры проекта
# ✅ Удаляет volumes проекта
# ✅ Удаляет образ проекта
# ✅ Не затрагивает другие проекты
clean:
	docker-compose down -v
	docker-compose rm -f
	docker rmi -f the-foundry-foundry-agent 2>/dev/null || true