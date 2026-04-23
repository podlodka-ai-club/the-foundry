.PHONY: build runagent shell clean test help

help:
	@echo "Доступные команды:"
	@echo "  make build                         - Собрать Docker образ"
	@echo "  make runagent task=XX              - Запустить агента для выполнения задачи из файла agent/tasks/XX/XX_task.md"
	@echo "  make runagent task=XX prompt="YY"  - Запустить агента для создания задачи XX из промта YY"
	@echo "  make test                          - Запустить все тесты"
	@echo "  make test test_name                - Запустить конкретный тест"
	@echo "  make shell                         - Открыть shell в контейнере"
	@echo "  make clean                         - Очистить Docker ресурсы"
	@echo ""
	@echo "Примеры:"
	@echo "  make runagent task=TF-1"
	@echo "  make runagent task=TF-2 prompt=\"Создай скрипт на python - выводящий на экран 'hello world'\""
	@echo "  make test"
	@echo "  make test test_providers.py"
	@echo "  make test test_core"

build:
	docker-compose build

runagent:
ifdef prompt
	docker-compose run --rm foundry-agent python -m agent.agent --task="$(task)" --prompt="$(prompt)"
else
	docker-compose run --rm foundry-agent python -m agent.agent --task="$(task)"
endif

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

shell:
	docker-compose run --rm foundry-agent /bin/bash

clean:
	docker-compose down -v
	docker system prune -f
