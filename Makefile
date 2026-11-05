CITY ?= 3552205

.PHONY: install test lint city site clean

install:
	uv sync --extra ingest

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

# Esqueleto ponta a ponta com dados sintéticos (sem rede)
city:
	uv run sombra run --city $(CITY) --demo

site: city
	@echo "abra web/index.html servindo a pasta web/: python3 -m http.server -d web 8000"

clean:
	rm -rf web/data data/processed
