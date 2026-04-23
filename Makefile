.PHONY: build runagent shell clean help

help:
	@echo "Доступные команды:"
	@echo "  make build              - Собрать Docker образ"
	@echo "  make runagent task=     - Запустить агента с задачей"
	@echo "  make shell              - Открыть shell в контейнере"
	@echo "  make clean              - Очистить Docker ресурсы"
	@echo ""
	@echo "Примеры:"
	@echo "  make runagent task=TF-1"
	@echo "  make runagent task=TF-2 prompt=\"Создай hello world скрипт\""

build:
	docker-compose build

runagent:
ifdef prompt
	docker-compose run --rm foundry-agent --task="$(task)" --prompt="$(prompt)"
else
	docker-compose run --rm foundry-agent --task="$(task)"
endif

shell:
	docker-compose run --rm foundry-agent /bin/bash

clean:
	docker-compose down -v
	docker system prune -f
