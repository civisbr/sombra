import { el, fmt, getJSON, loadCities, setupHeader } from "./common.js";

const { cities, code } = await loadCities();
const [meta, actions] = await Promise.all([getJSON(`data/${code}/meta.json`), getJSON(`data/${code}/actions.json`)]);
setupHeader(cities, code, meta);
document.getElementById("demo-banner").hidden = !meta.demo;
document.getElementById("ref-line").textContent =
  `Referência: ${meta.reference_date}. Fonte: ${meta.sources.map((s) => s.name).join("; ")}.`;
if (actions.cooling[0]) document.getElementById("radius").textContent = actions.cooling[0].radius_m;

function table(id, headers, rows) {
  const t = document.getElementById(id);
  t.replaceChildren(
    el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", { text: h })))),
    el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c) => el("td", { text: c }))))),
  );
  if (rows.length === 0) t.append(el("caption", { text: "Nenhum item atende aos critérios." }));
}

const sectorRow = (s) => [s.id, fmt(s.priority, 1), s.priority_label, fmt(s.population), fmt(s.pop_60plus), fmt(s.ndvi, 2)];
const sectorHead = ["Setor", "Índice", "Classe", "Moradores", "Com 60+", "NDVI"];

table("t-trees", sectorHead, actions.trees.map(sectorRow));
table(
  "t-cooling",
  ["Equipamento", "Tipo", "População prioritária ao alcance", "Setores"],
  actions.cooling.map((e) => [e.name, ({ ubs: "UBS", escola: "Escola", biblioteca: "Biblioteca" })[e.kind] ?? e.kind, fmt(e.population), e.sectors.join(", ")]),
);
table("t-active", sectorHead, actions.active_search.slice(0, 30).map(sectorRow));
