import { el, fmt, getJSON, loadCities, setupHeader } from "./common.js";

const { cities, code } = await loadCities();
const meta = await getJSON(`data/${code}/meta.json`);
setupHeader(cities, code, meta);
document.getElementById("demo-banner").hidden = !meta.demo;

const r = meta.robustness;
const pct = (v) => (v == null ? "—" : `${fmt(v * 100)}%`);
document.getElementById("robust-summary").textContent =
  `${meta.name}/${meta.uf} (${meta.reference_date}): sobreposição mínima do top ${fmt(r.fraction * 100)}% = ${pct(r.min_overlap)}; média = ${pct(r.mean_overlap)}.`;
const t = document.getElementById("t-robust");
t.append(
  el("thead", {}, el("tr", {}, el("th", { text: "Esquema alternativo" }), el("th", { text: "Sobreposição do top 10%" }))),
  el("tbody", {}, ...Object.entries(r.overlaps).map(([k, v]) => el("tr", {}, el("td", { text: k }), el("td", { text: pct(v) })))),
);
const n = meta.notes ?? {};
const cov = document.getElementById("coverage");
if (n.lst_scenes) {
  const ex = Object.entries(n.excluded_sectors ?? {}).map(([k, v]) => `${v} ${k}`).join(", ") || "nenhum";
  const fav = (n.included_sector_types ?? {})["1"] ?? 0;
  const eq = n.equipment ?? {};
  for (const t of [
    `${meta.n_sectors} setores urbanos, incluindo ${fav} de favelas e comunidades urbanas. Fora do índice: ${ex} (rurais e setores especiais do IBGE, quase sem moradores ou institucionais).`,
    `Calor: ${n.lst_scenes.length} datas Landsat de verão (${n.lst_scenes[0]} a ${n.lst_scenes[n.lst_scenes.length - 1]}), composto por mediana das anomalias.`,
    `Vegetação: mediana do NDVI do Sentinel-2 em ${(n.ndvi_scenes ?? []).length} datas de verão (${(n.ndvi_scenes ?? [""])[0]} a ${(n.ndvi_scenes ?? [""]).slice(-1)[0]}).`,
    `Equipamentos dentro do município (OpenStreetMap): ${eq.escola ?? 0} escolas, ${eq.ubs ?? 0} UBS e ${eq.biblioteca ?? 0} bibliotecas.`,
    "Distância à UBS: fora do índice por enquanto. As UBS do OpenStreetMap cobrem só parte das unidades e inflariam a prioridade onde falta mapeamento; voltará com uma fonte oficial (CNES).",
    "Valores sob sigilo do IBGE ficam vazios (nunca zero). Contagens e percentuais que resultariam em menos de 5 pessoas não são publicados. A renda é a mediana dos responsáveis com rendimento.",
  ]) cov.append(el("li", { text: t }));
} else cov.append(el("li", { text: "Dados sintéticos de demonstração." }));

const ul = document.getElementById("sources");
for (const s of meta.sources) ul.append(el("li", { text: `${s.name}: ${s.use}` }));
