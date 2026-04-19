#!/bin/make

SVC ?=
TAIL ?= 200

.PHONY: help start stop restart build rebuild clean clean-all prune status ps logs logs-tail logs-file logs-service start-service stop-service restart-service shell shell-db shell-backend shell-frontend shell-admin shell-vault format lint setup-local

help:
	@echo "CLE Engine Development Commands"
	@echo "================================"
	@echo "Core"
	@echo "  make start                 - Start all services"
	@echo "  make stop                  - Stop all services"
	@echo "  make restart               - Restart all services"
	@echo "  make status                - Show service status"
	@echo "  make ps                    - Alias of status"
	@echo ""
	@echo "Build & Cleanup"
	@echo "  make build                 - Build all images"
	@echo "  make rebuild               - Rebuild images without cache"
	@echo "  make clean                 - Stop and remove containers + named volumes"
	@echo "  make clean-all             - Full cleanup (containers, volumes, images, cache)"
	@echo "  make prune                 - Prune unused docker resources"
	@echo ""
	@echo "Per-service control"
	@echo "  make start-service SVC=db"
	@echo "  make stop-service SVC=frontend"
	@echo "  make restart-service SVC=backend"
	@echo "  make logs-service SVC=admin"
	@echo "  make shell SVC=backend"
	@echo ""
	@echo "Logs"
	@echo "  make logs                  - Follow all compose logs"
	@echo "  make logs-tail             - Tail compose logs (TAIL=200 by default)"
	@echo "  make logs-file             - List persisted rotated app logs volume"
	@echo ""
	@echo "Convenience shells"
	@echo "  make shell-db"
	@echo "  make shell-backend"
	@echo "  make shell-frontend"
	@echo "  make shell-admin"
	@echo "  make shell-vault"

start:
	@echo "Starting development services..."
	docker-compose up -d
	@docker-compose rm -f -s -v vault-init >/dev/null 2>&1 || true
	@echo "Services started! Access them at:"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend:  http://localhost:8000"
	@echo "  Admin:    http://localhost:8501"
	@echo "  Docs:     http://localhost:8000/docs"

stop:
	@echo "Stopping development services..."
	docker-compose down

restart: stop start

build:
	@echo "Building Docker images..."
	docker-compose build

rebuild:
	@echo "Rebuilding Docker images (no cache)..."
	docker-compose build --no-cache

clean:
	@echo "Cleaning containers and named volumes..."
	docker-compose down -v --remove-orphans

clean-all: clean
	@echo "Pruning images, networks, and build cache..."
	docker system prune -af --volumes

prune:
	@echo "Pruning unused Docker resources..."
	docker system prune -f

status:
	docker-compose ps

ps: status

logs:
	docker-compose logs -f

logs-tail:
	docker-compose logs --tail=$(TAIL)

logs-service:
	@test -n "$(SVC)" || (echo "Usage: make logs-service SVC=<service>" && exit 1)
	docker-compose logs -f $(SVC)

logs-file:
	docker run --rm -v cle-engine-app-logs:/logs alpine:3.20 sh -c "ls -lah /logs || true"

start-service:
	@test -n "$(SVC)" || (echo "Usage: make start-service SVC=<service>" && exit 1)
	docker-compose up -d $(SVC)

stop-service:
	@test -n "$(SVC)" || (echo "Usage: make stop-service SVC=<service>" && exit 1)
	docker-compose stop $(SVC)

restart-service:
	@test -n "$(SVC)" || (echo "Usage: make restart-service SVC=<service>" && exit 1)
	docker-compose restart $(SVC)

shell:
	@test -n "$(SVC)" || (echo "Usage: make shell SVC=<service>" && exit 1)
	docker-compose exec $(SVC) sh

shell-db:
	docker-compose exec db psql -U admin -d cle_engine

shell-backend:
	docker-compose exec backend sh

shell-frontend:
	docker-compose exec frontend sh

shell-admin:
	docker-compose exec admin sh

shell-vault:
	docker-compose exec vault sh

format:
	@echo "Formatting Python code..."
	python -m ruff format app

lint:
	@echo "Linting Python code..."
	python -m ruff check app

setup-local:
	@echo "Creating virtual environment..."
	python3 -m venv .venv
	@echo "Virtual environment created"
	@echo "Next, run: source .venv/bin/activate"
