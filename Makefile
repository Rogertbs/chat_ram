COMPOSE := docker compose
DB_COMPOSE := docker compose --env-file .env -f postgres18/docker-compose.yml
PY := .venv/bin/python

.PHONY: help prod dev db build up mock prep down logs test

help:
	@echo "Alvos disponíveis:"
	@echo "  make prod  - sobe PostgreSQL 18 + serviço (build + up)"
	@echo "  make dev   - prod + banco mock + preparação (ambiente de teste pronto)"
	@echo "  make db    - sobe só o PostgreSQL 18"
	@echo "  make build - constrói a imagem do serviço"
	@echo "  make up    - sobe o serviço"
	@echo "  make mock  - (re)gera o banco mock"
	@echo "  make prep  - roda a preparação (embeddings) no mock"
	@echo "  make down  - derruba serviço e banco"
	@echo "  make logs  - acompanha os logs do serviço"
	@echo "  make test  - roda os testes no host"

prod: db
	$(COMPOSE) up -d --build --wait

dev: db build mock prep
	$(COMPOSE) up -d --force-recreate --wait

db:
	$(DB_COMPOSE) up -d --build --wait

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --wait

mock: build
	$(COMPOSE) run --rm app python mock/gerar_banco.py --recriar

prep: build
	$(COMPOSE) run --rm app python -m chat_ram.preparacao

down:
	$(COMPOSE) down
	$(DB_COMPOSE) down

logs:
	$(COMPOSE) logs -f app

test:
	$(PY) -m pytest -q
