COMPOSE := docker compose
DB_COMPOSE := docker compose --env-file .env -f postgres18/docker-compose.yml
PY := .venv/bin/python

.PHONY: help prod dev db build up mock prep down logs test ui filtro

help:
	@echo "Alvos disponíveis:"
	@echo "  make prod   - sobe PostgreSQL 18 + serviço (build + up)"
	@echo "  make dev    - prod + banco mock + preparação (ambiente de teste pronto)"
	@echo "  make ui     - sobe a Open WebUI em http://localhost:3000 apontada para a API"
	@echo "  make filtro - instala/atualiza o filtro de guardrail na Open WebUI"
	@echo "  make db     - sobe só o PostgreSQL 18"
	@echo "  make build  - constrói a imagem do serviço"
	@echo "  make up     - sobe o serviço"
	@echo "  make mock   - (re)gera o banco mock"
	@echo "  make prep   - roda a preparação (embeddings) no mock"
	@echo "  make down   - derruba serviço, UI e banco"
	@echo "  make logs   - acompanha os logs do serviço"
	@echo "  make test   - roda os testes no host"

prod: db
	$(COMPOSE) up -d --build --wait

dev: db build mock prep
	$(COMPOSE) up -d --force-recreate --wait

ui: prod
	$(COMPOSE) --profile ui up -d openwebui

filtro:
	$(PY) openwebui/instalar_filtro.py

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
	$(COMPOSE) --profile ui down
	$(DB_COMPOSE) down

logs:
	$(COMPOSE) logs -f app

test:
	$(PY) -m pytest -q
