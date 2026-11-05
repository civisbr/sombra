<p align="center">
  <img src="docs/assets/logo.png" alt="Sombra" width="420" />
</p>

# Sombra

Mapa de calor urbano × vulnerabilidade para priorizar arborização e proteção. Uma iniciativa [CivisBR](https://github.com/civisbr).

> Em quais quarteirões da cidade o calor extremo atinge quem tem menos defesa, e onde plantar árvores e abrir pontos de resfriamento primeiro?

Ondas de calor matam no Brasil, e matam de forma desigual. O Sombra é uma ferramenta aberta e padronizada, aplicável a qualquer município brasileiro, que:

1. mapeia a temperatura de superfície no verão por setor censitário (Landsat 8/9);
2. combina com vulnerabilidade social e demográfica do Censo 2022;
3. gera um índice de prioridade e três listas acionáveis: onde **arborizar**, onde abrir **pontos de resfriamento** e onde a atenção primária deve fazer **busca ativa** de idosos.

Cidade-piloto: Sorocaba-SP (`cities/3552205.toml`). O pipeline recebe o código IBGE de 7 dígitos como parâmetro.

**O que não é:** não mede a temperatura do ar dentro das casas e não é sistema de alerta meteorológico (isso é do INMET/Defesa Civil). Calor de superfície não é temperatura do ar.

![Referência de design do site](docs/assets/design-referencia.png)

## Estado atual

| Fase | Entrega | Estado |
|---|---|---|
| 0 | Fundação: `uv`, `ruff`, `pytest`, Makefile, config por cidade | feito |
| 1 | Calor de superfície (Landsat 8/9, últimos 3 verões) por setor | feito para Sorocaba; falta a comparação com estações INMET e o composto 2013–presente |
| 2 | Vulnerabilidade: Censo 2022, NDVI, distância à UBS | feito para Sorocaba, sem a distância à UBS (falta fonte oficial) |
| 3 | Índice, sensibilidade e listas de ação | feito; **pendentes:** PCA na sensibilidade e filtro de calçada/praça (OSM) |
| 4 | Site: mapa, prioridades, metodologia, dados abertos | no ar, com dados reais de Sorocaba |
| 5–6 | Escala, validação entre municípios, ECOSTRESS | pendente |

Sorocaba roda com dados reais: 1.091 setores urbanos do Censo 2022 (1.051 comuns e 40 de favelas e comunidades urbanas), calor de 31 datas Landsat e NDVI de 9 datas Sentinel-2 (o verão 2023/24 tem só 1 data utilizável). A sobreposição mínima do top 10% sob pesos alternativos é de 76% (meta: 70%). Desvios em relação ao `PROJECT.md`:

- idosos são **60+** (o Censo agregado por setor só traz as faixas 60–69 e 70+);
- a renda é a **mediana** dos responsáveis com rendimento (responsáveis sem rendimento ficam fora);
- a **distância à UBS está fora do índice**: as UBS do OpenStreetMap cobrem só parte das unidades e inflariam a prioridade onde falta mapeamento. Volta com uma fonte oficial (CNES);
- contagens e percentuais que resultem em menos de 5 pessoas não são publicados.

A validação com temperatura do ar (INMET) e com mortalidade ainda não foi feita. O modo sintético (`sombra/demo.py`) continua só para testes e desenvolvimento.

## Uso

```bash
make install            # uv sync --extra ingest
make test               # pytest
make lint               # ruff
make city CITY=3552205  # dados reais: baixa IBGE/Landsat/Sentinel-2/OSM (cache em data/) -> web/data/
make demo CITY=3552205  # dados sintéticos, sem rede, em data/demo/
python3 -m http.server -d web 8000   # abre o site em http://localhost:8000
```

Os resultados publicados ficam versionados em `web/data/<ibge>/`; o deploy só publica o que está no repositório.

## Publicação

| Site | Onde | Workflow | Conteúdo |
|---|---|---|---|
| Projeto Sombra | GitHub Pages: https://civisbr.github.io/sombra/ | `pages.yml` (pasta `site/`) | o que é, como funciona, cidades, limitações |
| Sombra em Sorocaba | Cloudflare Pages: https://sombra-dwm.pages.dev/ | `deploy.yml` (pasta `web/`) | mapa, prioridades, metodologia e dados de Sorocaba |

O GitHub Pages precisa estar em *Settings → Pages → Source: GitHub Actions* (`gh api -X PUT repos/civisbr/sombra/pages -f build_type=workflow`). O deploy no Cloudflare roda testes, gera os dados de Sorocaba e publica `web/`. Configuração única:

1. O workflow cria o projeto `sombra` se ele não existir. A Cloudflare escolhe o subdomínio (hoje `sombra-dwm.pages.dev`, porque `sombra` estava ocupado); se mudar, atualizar os links em `site/index.html` e neste README.
2. Criar um token de API dedicado, com a permissão *Cloudflare Pages: Edit* só para a conta e com data de expiração.
3. Em Settings → Environments, criar `cloudflare-pages` restrito à branch `main` e cadastrar nele, como *environment secrets*, `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID`.


## Metodologia (resumo)

- **Calor:** `ST_B10` do Landsat C2 L2 (`K = DN × 0.00341802 + 149.0`), máscara por `QA_PIXEL`, anomalia de cada pixel contra a mediana urbana da cena, mediana das anomalias, média e P90 por setor.
- **Índice:** média geométrica de exposição, sensibilidade e baixa capacidade de adaptação, cada uma em percentil dentro da cidade, com pesos iguais e documentados.
- **Robustez:** pesos alternativos (um componente dobrado, um indicador removido) e sobreposição do top 10%.
- **Validação planejada:** LST × temperatura do ar (INMET), comparação com estudos locais e, entre municípios, excesso de mortalidade em ondas de calor (SIM).

Detalhes, limitações e referências científicas em [`PROJECT.md`](PROJECT.md) e na página de metodologia do site.

## Estrutura

```
sombra/
  cities/        # <codigo_ibge>.toml: bbox, anos, estações INMET
  sombra/
    ingest/ heat/ vulnerability/ index/ actions/ validate/ publish/
    demo.py pipeline.py cli.py
  web/           # site estático (MapLibre GL + mapa-base OpenFreeMap/OSM, sem rastreio próprio)
  tests/
```

Código e identificadores em inglês; documentação e site em português.

## Ética e dados

Só agregados por setor censitário; nenhum dado individual. O foco é onde investir, não "onde é ruim". Código sob [MIT](LICENSE). Dados derivados sob CC BY 4.0, citando NASA/USGS, ESA/Copernicus, IBGE, INMET e DATASUS.
