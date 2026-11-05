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
const ul = document.getElementById("sources");
for (const s of meta.sources) ul.append(el("li", { text: `${s.name}: ${s.use}` }));
