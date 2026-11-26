.PHONY: install test lint format run up down sample-tender

install:
	pip install -r requirements-dev.txt

test:
	pytest -q

lint:
	ruff check app tests scripts

format:
	ruff format app tests scripts

run:
	uvicorn app.main:app --reload

up:
	docker compose up --build

down:
	docker compose down

sample-tender:
	python scripts/build_sample_tender.py
