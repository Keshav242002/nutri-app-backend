PYTHON   := .venv/bin/python
PYTEST   := .venv/bin/pytest
RUFF     := .venv/bin/ruff
BLACK    := .venv/bin/black
MYPY     := .venv/bin/mypy
MANAGE   := $(PYTHON) manage.py
PG_BIN   := /opt/homebrew/opt/postgresql@16/bin
export PATH := $(PG_BIN):$(PATH)

.PHONY: install migrate seed superuser run run-asgi test lint format dbreset shell worker beat fetch-usda build-seed

## Setup

install:
	uv pip install -r requirements/dev.txt

migrate:
	$(MANAGE) migrate

seed:
	$(MANAGE) seed_recipes

superuser:
	$(MANAGE) createsuperuser

## Dev loop

run:
	$(MANAGE) runserver

run-asgi:
	.venv/bin/uvicorn nutriplan.asgi:application --reload

test:
	$(PYTEST)

lint:
	$(RUFF) check .
	$(BLACK) --check .
	$(MYPY) apps/ core/

format:
	$(RUFF) check --fix .
	$(BLACK) .

## Celery (from M6)

worker:
	.venv/bin/celery -A nutriplan worker -l info

beat:
	.venv/bin/celery -A nutriplan beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

## DB ops

dbreset:
	@echo "WARNING: This will drop and recreate the nutriplan database."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	dropdb --if-exists -U nutriplan nutriplan
	createdb -O nutriplan nutriplan
	$(MANAGE) migrate

shell:
	$(MANAGE) shell

## Seed data

build-seed:
	uv run python scripts/build_seed_data.py

fetch-usda:
	uv run python scripts/fetch_usda_nutrition.py
