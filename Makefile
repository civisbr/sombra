CITY ?= 3552205

.PHONY: install test lint lst city demo clean

install:
	uv sync --extra ingest

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

# Dados reais (baixa IBGE, Landsat, Sentinel-2 e OSM na primeira vez; guarda cache em data/)
lst:
	uv run sombra lst --city $(CITY)

city: lst
	uv run sombra run --city $(CITY)

# Esqueleto ponta a ponta com dados sintéticos (sem rede), fora de web/data
demo:
	uv run sombra run --city $(CITY) --demo --out data/demo/$(CITY)

clean:
	rm -rf data/demo data/processed
