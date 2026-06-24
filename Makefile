.PHONY: install dev browsers lint fmt test cov clean docker-build docker-up

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

browsers:
	python -m playwright install chromium

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff format .
	ruff check --fix .

test:
	pytest

cov:
	coverage run -m pytest && coverage report

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

docker-build:
	docker build -t scrapehub:latest .

docker-up:
	docker compose up --build
