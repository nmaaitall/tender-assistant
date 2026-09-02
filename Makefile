.PHONY: install test lint format run up down

install:
	pip install -r requirements-dev.txt

test:
	pytest -q

lint:
	ruff check app tests

format:
	ruff format app tests

run:
	uvicorn app.main:app --reload

up:
	docker compose up --build

down:
	docker compose down
