# Sombra — mapa de calor urbano × vulnerabilidade para priorizar arborização e proteção

> Em quais quarteirões da cidade o calor extremo atinge quem tem menos defesa, e onde plantar árvores e abrir pontos de resfriamento primeiro?

## 1. Contexto e propósito

Ondas de calor matam no Brasil, e matam de forma desigual. Bairros pobres, densos e sem árvores ficam mais quentes, e é lá que vivem mais idosos e pessoas com menos recursos para se proteger. Estudos que cruzam temperatura de superfície com renda existem, mas são feitos **cidade por cidade**, com métodos diferentes, e raramente viram uma lista acionável para a prefeitura.

O Sombra é uma ferramenta **aberta e padronizada**, aplicável a qualquer município brasileiro, que:
1. mapeia a temperatura de superfície no verão por setor censitário (Landsat 8/9);
2. combina com vulnerabilidade social e demográfica do Censo 2022;
3. gera um **índice de prioridade** e listas acionáveis: onde arborizar, onde instalar pontos de resfriamento, onde a atenção primária deve fazer busca ativa de idosos em ondas de calor.

**Cidade-piloto:** Sorocaba-SP (configurável; o pipeline deve receber o código IBGE do município como parâmetro).

**O que NÃO é:** não mede a temperatura do ar dentro das casas; não é sistema de alerta meteorológico (isso é do INMET/Defesa Civil).

## 2. Base científica

- **Monteiro dos Santos et al. (2024)**. Twenty-first-century demographic and social inequalities of heat-related deaths in Brazilian urban areas. PMC10807764. 48.075 mortes em excesso por ondas de calor em 14 regiões metropolitanas (2000–2018), mais de 20× as mortes por deslizamentos no mesmo período. Mais vulneráveis: baixa escolaridade, pretos e pardos, idosos, mulheres. Calor extremo como "desastre negligenciado".
- **Debone et al. (2025)**, *Atmosphere* 16(7). The Cost of Heat: Health and Economic Burdens in Three Brazilian Cities. 2.319 mortes atribuíveis ao calor em São Paulo, Campinas e Marília (2004–2018); risco relativo maior em Marília, uma cidade média, que na capital. Relevante para cidades do interior.
- **Geirinhas et al. (2020)**, *Int. J. Biometeorology*. Heat-related mortality in Rio de Janeiro. Calor acumulado em dias consecutivos mata mais que dias quentes isolados.
- **Estudos locais Landsat × renda**: Santos (Censo 2010, Spearman por setor), Presidente Prudente/Três Lagoas (diurno e noturno), São Paulo (Landsat 8/9 × renda por distrito). Usar como referência metodológica e para comparação de resultados.
- **Cautela da literatura:** índices de vulnerabilidade ao calor são difíceis de validar e tendem a virar índices de pobreza genéricos (ver o índice para o Rio, SN Applied Sciences 2020, s42452-020-03750-7).

## 3. Fontes de dados

| Dado | Fonte | Acesso | Observações |
|---|---|---|---|
| Temperatura de superfície (LST) | Landsat 8/9 Collection 2 Level-2, banda `ST_B10` | STAC do Microsoft Planetary Computer (leitura gratuita) ou USGS/Google Earth Engine | Kelvin = `ST_B10 × 0.00341802 + 149.0`. Máscara de nuvem por `QA_PIXEL`. 30 m (reamostrado de 100 m). Passagem ~10h local. |
| LST noturna (opcional) | ECOSTRESS (NASA, ISS) | NASA Earthdata (LP DAAC), login gratuito | Horários variáveis, inclusive noturnos. Cobertura irregular. |
| Vegetação | Sentinel-2 L2A (NDVI) e/ou MapBiomas | Planetary Computer / Copernicus; MapBiomas | Cobertura arbórea urbana. |
| Setores censitários (malha) | IBGE, Censo 2022 | Download oficial | Unidade de análise principal. |
| Variáveis do Censo 2022 | IBGE, agregados por setor censitário | Download oficial / SIDRA | População por idade, cor/raça, domicílios. **Verificar** se renda por setor do Censo 2022 já foi divulgada; senão, usar proxy disponível ou Censo 2010 compatibilizado, e declarar isso. |
| Temperatura do ar (calibração) | INMET (estações automáticas); ERA5-Land | Portal INMET; Copernicus CDS | Para relacionar LST e temperatura do ar e definir ondas de calor. |
| Mortalidade (validação) | DATASUS SIM, `DOUFAAAA.dbc` | FTP DATASUS; lib `pysus` | Campos: `DTOBITO`, `CAUSABAS`, `CODMUNRES`, `IDADE`, `RACACOR`, `ESC`. **Só tem município de residência, não bairro.** |
| Equipamentos públicos | CNES (UBS), escolas, praças | DATASUS, INEP, OpenStreetMap | Candidatos a pontos de resfriamento. |

**Pegadinhas conhecidas:**
- **LST não é temperatura do ar.** Asfalto a 45 °C não significa ar a 45 °C. O produto fala em "calor de superfície" e usa a calibração com estações para qualquer afirmação sobre risco.
- O SIM público não permite validar o índice **dentro** da cidade (não há bairro). A validação intra-urbana exige parceria com a secretaria municipal de saúde (óbitos geocodificados). A validação com dados abertos é **entre municípios**.
- Código de município: SIM/DATASUS usa 6 dígitos, IBGE usa 7.

## 4. Metodologia

### 4.1 Calor de superfície
1. Selecionar todas as cenas Landsat 8/9 de verão (dez–mar), 2013–presente, cobrindo o município, com cobertura de nuvem aceitável.
2. Aplicar máscara de nuvem/sombra (`QA_PIXEL`) e converter para °C.
3. Para cada cena, calcular a **anomalia** de cada pixel em relação à mediana urbana da própria cena. Isso remove a diferença entre dias mais quentes e mais frios.
4. Compor a mediana das anomalias por pixel e agregar por setor censitário (média e percentil 90).
5. Repetir separadamente para os anos mais recentes (ex.: últimos 3 verões) para captar mudanças.

### 4.2 Vulnerabilidade
Variáveis por setor (todas documentadas, com fonte e ano):
- % população com 65+ anos e % com 0–4 anos;
- renda (ou proxy), % pretos e pardos;
- densidade de moradores por domicílio;
- cobertura vegetal (NDVI médio, % de copa);
- distância à UBS mais próxima.

### 4.3 Índice de prioridade
- Padronizar as variáveis (z-score ou percentil dentro da cidade).
- Índice = combinação de **exposição** (anomalia de LST) × **sensibilidade** (idade, densidade) × **baixa capacidade de adaptação** (renda, vegetação, acesso à UBS).
- Pesos: começar com pesos iguais e documentados; oferecer análise de sensibilidade (pesos alternativos, PCA). **Não** esconder os pesos.
- Saídas acionáveis:
  - **Arborização:** setores com alta anomalia + baixa vegetação + alta vulnerabilidade, com área de calçada/praça disponível (OSM).
  - **Pontos de resfriamento:** equipamentos públicos (escolas, UBS, bibliotecas) que cobrem os setores prioritários num raio caminhável (ex.: 500 m).
  - **Busca ativa:** setores com mais idosos em calor alto, para a atenção primária priorizar em alertas de onda de calor.

### 4.4 Validação
- **Física:** comparar a LST média com a temperatura do ar nas estações INMET da região; reportar a correlação.
- **Externa:** comparar o padrão renda × LST com os estudos de Santos, Presidente Prudente e São Paulo.
- **Desfecho (entre municípios):** para os municípios onde o Sombra rodar, calcular o excesso de mortalidade em ondas de calor (SIM + INMET/ERA5, razão observado/esperado como em Monteiro dos Santos et al.) e testar se o índice municipal agregado se associa a ele.
- **Robustez:** o ranking dos setores prioritários deve ser estável sob pesos alternativos (reportar a sobreposição do top 10%).

## 5. Arquitetura e stack

- **Linguagem:** Python 3.12 com `uv`.
- **Raster:** `pystac-client` + `planetary-computer` + `stackstac` ou `odc-stac`; `xarray`/`rioxarray`; `rasterstats` ou `exactextract` para zonal stats por setor.
- **Tabular/geo:** DuckDB (extensão `spatial`) + Parquet/GeoParquet; `geopandas` só onde necessário.
- **Front:** site estático (Cloudflare Pages ou GitHub Pages) com MapLibre GL + PMTiles (gerados com `tippecanoe`). Camadas: calor, vulnerabilidade, prioridade, equipamentos. Página por cidade, URL `/<codigo_ibge>`.
- **Configuração por município:** `cities/<codigo_ibge>.toml` (bbox, anos, estações INMET de referência).

### Estrutura do repositório

```
sombra/
  PROJECT.md
  pyproject.toml
  Makefile
  cities/
    3552205.toml          # Sorocaba (piloto)
  sombra/
    ingest/        # landsat.py, ecostress.py, sentinel2.py, ibge.py, inmet.py, sim.py, osm.py
    heat/          # lst.py (conversão, máscara, anomalia, composição)
    vulnerability/ # census.py, indicators.py
    index/         # priority.py, sensitivity.py
    actions/       # trees.py, cooling_points.py, active_search.py
    validate/      # air_vs_lst.py, heatwave_mortality.py, robustness.py
    publish/       # tiles.py, export_web.py
  data/            # gitignored
  notebooks/
  web/
  tests/
```

## 6. Fases e entregáveis

**Fase 0 — Fundação**
- Repo, `uv`, `ruff`, `pytest`, Makefile, config por cidade.
- Aceite: `make test` verde; `make city CITY=3552205` roda o esqueleto ponta a ponta com stubs.

**Fase 1 — Calor de superfície (piloto)**
- Pipeline LST Landsat para o piloto: cenas de verão, máscara, anomalia, composição e agregação por setor.
- Aceite: mapa coerente (área central e industrial quentes, áreas verdes e represas frias); correlação LST × temperatura do ar das estações reportada.

**Fase 2 — Vulnerabilidade**
- Indicadores do Censo 2022 por setor + NDVI + distância à UBS.
- Aceite: 100% dos setores urbanos com indicadores ou motivo documentado de ausência.

**Fase 3 — Índice e ações**
- Índice de prioridade, análise de sensibilidade e as três listas acionáveis.
- Aceite: top 10% de setores estável (sobreposição ≥ 70%) sob pesos alternativos.

**Fase 4 — Site**
- Mapa interativo + página de metodologia e limitações + download dos dados (GeoParquet/CSV).
- Aceite: site no ar com o piloto.

**Fase 5 — Escala**
- Rodar para outras cidades (começar pelas 14 RMs do estudo de referência e cidades médias de SP).
- Validação entre municípios com o SIM (seção 4.4).

**Fase 6 (opcional)**
- Camada noturna com ECOSTRESS.
- Integração com o projeto Fôlego (mesma base SIH/SIM) numa plataforma comum clima × SUS.
- Relatório para a prefeitura e câmara do piloto.

## 7. Limitações a declarar publicamente

- LST diurna (~10h) ≠ temperatura do ar ≠ calor dentro de casa à noite.
- Resolução térmica nativa de 100 m: não enxerga a escala de rua ou quarteirão pequeno.
- Índice composto depende de escolhas de peso; publicadas e com análise de sensibilidade.
- Sem dados públicos de óbito por bairro, a validação intra-urbana depende de parcerias.
- Exceções reais existem: bairros de baixa renda com muita vegetação podem ser mais frescos. O índice deve mostrar isso, não esconder.

## 8. Ética e dados

- Publicar só agregados por setor; nenhum dado individual.
- Evitar linguagem estigmatizante sobre bairros; o foco é onde investir, não "onde é ruim".
- Licença do código: MIT ou Apache-2.0. Dados derivados: CC-BY 4.0, citando NASA/USGS, ESA/Copernicus, IBGE, INMET e DATASUS.

## 9. Convenções para o Claude Code

- Código e identificadores em inglês; documentação e site em português.
- Todo passo é parametrizado por `CITY` (código IBGE de 7 dígitos) e idempotente, com cache em `data/raw/`.
- Testar a conversão de LST contra valores conhecidos de uma cena de referência.
- Testar a agregação zonal com geometria sintética de resultado conhecido.
- Nenhum número no site sem fonte e data ao lado.
