import { el, getJSON, loadCities, setupHeader } from "./common.js";

const { cities, code } = await loadCities();
const meta = await getJSON(`data/${code}/meta.json`);
setupHeader(cities, code, meta);
document.getElementById("demo-banner").hidden = !meta.demo;
document.getElementById("ref-line").textContent =
  `${meta.name}/${meta.uf} · ${meta.n_sectors} setores · referência: ${meta.reference_date}.`;

const files = [
  ["sectors.csv", "CSV (planilha)"],
  ["sectors.geojson", "GeoJSON (mapas)"],
  ["sectors.parquet", "GeoParquet (análise)"],
  ["actions.json", "Listas de ação (JSON)"],
  ["meta.json", "Metadados, fontes e robustez (JSON)"],
];
const ul = document.getElementById("downloads");
for (const [f, label] of files) {
  const head = await fetch(`data/${code}/${f}`, { method: "HEAD" }).catch(() => null);
  if (!head || !head.ok) continue;
  ul.append(el("li", {}, el("a", { href: `data/${code}/${f}`, download: "", text: label }), ` (${f})`));
}

const fields = {
  id: "Código do setor",
  lst_anomaly_mean: "Anomalia média de calor de superfície vs. mediana urbana da cena (°C)",
  lst_anomaly_p90: "Percentil 90 da anomalia (°C)",
  lst_pixels: "Pixels válidos no setor",
  population: "Moradores",
  pop_60plus: "Moradores com 60+ anos (estimado a partir do %)",
  pct_60plus: "% com 60+ anos",
  pct_0_4: "% com 0–4 anos",
  income: "Renda mediana dos responsáveis com rendimento (R$, Censo 2022)",
  pct_black_brown: "% pretos e pardos",
  persons_per_household: "Moradores por domicílio",
  ndvi: "NDVI médio",
  dist_ubs_m: "Distância à UBS mais próxima (m); vazio até haver fonte oficial (CNES)",
  exposure: "Componente de exposição (0–1, percentil)",
  sensitivity: "Componente de sensibilidade (0–1)",
  low_adaptation: "Componente de baixa capacidade de adaptação (0–1)",
  priority: "Índice de prioridade (0–100)",
  priority_class: "Classe por quartil (0 menor … 3 muito alta; -1 sem dado)",
  priority_label: "Rótulo da classe",
};
const tb = document.getElementById("fields");
for (const [k, v] of Object.entries(fields)) tb.append(el("tr", {}, el("td", {}, el("code", { text: k })), el("td", { text: v })));
