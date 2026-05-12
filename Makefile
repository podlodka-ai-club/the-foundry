.PHONY: help build up down restart logs clean install test status

# Цвета для вывода
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Показать список доступных команд
	@echo "$(GREEN)The Foundry - Makefile команды:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

build: ## Собрать Docker образы
	@echo "$(YELLOW)Сборка Docker образов...$(NC)"
	docker-compose build --no-cache

up: ## Запустить все сервисы
	@echo "$(GREEN)Запуск сервисов...$(NC)"
	docker-compose up

up-d: ## Запустить все сервисы в фоновом режиме
	@echo "$(GREEN)Запуск сервисов в фоне...$(NC)"
	docker-compose up -d

down: ## Остановить все сервисы
	@echo "$(YELLOW)Остановка сервисов...$(NC)"
	docker-compose down

restart: ## Перезапустить все сервисы
	@echo "$(YELLOW)Перезапуск сервисов...$(NC)"
	docker-compose restart

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-api: ## Показать логи API
	docker-compose logs -f api

logs-worker: ## Показать логи worker
	docker-compose logs -f worker

logs-web: ## Показать логи web
	docker-compose logs -f web

logs-pr: ## Показать логи pr-feedback
	docker-compose logs -f pr-feedback

status: ## Показать статус контейнеров
	@echo "$(BLUE)Статус контейнеров:$(NC)"
	docker-compose ps

clean: ## Удалить контейнеры, образы и volumes
	@echo "$(YELLOW)Очистка Docker ресурсов...$(NC)"
	docker-compose down -v --rmi local
	rm -rf data/*.sqlite data/*.sqlite-*

clean-data: ## Удалить только данные (БД и worktrees)
	@echo "$(YELLOW)Очистка данных...$(NC)"
	rm -rf data/*.sqlite data/*.sqlite-*
	rm -rf worktrees/*

install: ## Установить зависимости локально (без Docker)
	@echo "$(GREEN)Установка зависимости Python...$(NC)"
	uv sync
	@echo "$(GREEN)Установка зависимости Node.js...$(NC)"
	cd web && npm install

dev-api: ## Запустить API локально (без Docker)
	uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8001

dev-worker: ## Запустить worker локально (без Docker)
	uv run foundry run

dev-web: ## Запустить frontend локально (без Docker)
	cd web && npm run dev -- --host 0.0.0.0 --port 5174

test: ## Запустить тесты
	@echo "$(GREEN)Запуск тестов Python...$(NC)"
	uv run pytest
	@echo "$(GREEN)Проверка типов TypeScript...$(NC)"
	cd web && npx tsc --noEmit
	@echo "$(GREEN)Сборка frontend...$(NC)"
	cd web && npm run build

rebuild: down build up ## Полная пересборка и запуск

setup: ## Первоначальная настройка проекта
	@echo "$(GREEN)Настройка проекта...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Копирование .env.example -> .env$(NC)"; \
		cp .env.example .env; \
		echo "$(YELLOW)⚠️  Отредактируйте .env файл перед запуском!$(NC)"; \
	else \
		echo "$(GREEN)✓ .env уже существует$(NC)"; \
	fi
	@echo "$(GREEN)Создание директорий...$(NC)"
	mkdir -p data worktrees
	@echo "$(GREEN)✓ Настройка завершена$(NC)"

gh-auth: ## Проверить авторизацию GitHub CLI
	@echo "$(BLUE)Проверка GitHub CLI...$(NC)"
	gh auth status

gh-login: ## Авторизоваться в GitHub CLI
	gh auth login

shell-api: ## Войти в shell контейнера API
	docker-compose exec api bash

shell-worker: ## Войти в shell контейнера worker
	docker-compose exec worker bash

shell-web: ## Войти в shell контейнера web
	docker-compose exec web sh