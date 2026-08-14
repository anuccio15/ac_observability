.PHONY: up down logs test integration-test migrate backup

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app migrate db

test:
	python -m pytest

integration-test:
	docker compose --profile test run --rm test

migrate:
	docker compose run --rm migrate

backup:
	./scripts/backup.sh
