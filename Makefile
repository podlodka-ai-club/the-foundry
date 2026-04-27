.PHONY: run test test-unit test-int help

help:
	@echo "Доступные команды:"
	@echo "  make run                           - Запустить pipeline один раз (foundry run)"
	@echo "  make test                          - Запустить все тесты"
	@echo "  make test-unit                     - Запустить только unit тесты (быстрые)"
	@echo "  make test-int                      - Запустить только интеграционные тесты"
	@echo "  make test filter=test_name         - Запустить конкретный тест"

run:
	uv run foundry run

test:
ifdef filter
	@if echo "$(filter)" | grep -q "\.py$$"; then \
		uv run pytest tests/$(filter) -v; \
	else \
		uv run pytest tests/$(filter).py -v; \
	fi
else
	uv run pytest tests/ -v
endif

test-unit:
	uv run pytest tests/ -v -m "not integration"

test-int:
	uv run pytest tests/ -v -m integration
