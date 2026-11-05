import { CLASS_COLORS, CLASS_NAMES, el, fmt, getJSON, loadCities, setupHeader } from "./common.js";

const LAYERS = {
  priority: { prop: "priority_class", title: "Prioridade" },
  heat: { prop: "lst_anomaly_mean", title: "Calor de superfície (anomalia, °C)" },
  vuln: { prop: "vuln", title: "Vulnerabilidade" },
  veg: { prop: "ndvi", title: "Cobertura vegetal (NDVI)" },
};
const RAMPS = {
  heat: ["#f6e3a1", "#f2c066", "#ea8d45", "#c8503c"],
  vuln: ["#f6e3a1", "#f2c066", "#ea8d45", "#c8503c"],
  veg: ["#e6f0c8", "#b5d57a", "#6fb04a", "#2f7d3a"],
};
const EQUIP_COLORS = { ubs: "#c8503c", escola: "#0f3d22", biblioteca: "#5b6fb5" };
const EQUIP_NAMES = { ubs: "UBS", escola: "Escola", biblioteca: "Biblioteca" };

const { cities, code } = await loadCities();
const base = `data/${code}`;
const [meta, gj, actions] = await Promise.all([
  getJSON(`${base}/meta.json`),
  getJSON(`${base}/sectors.geojson`),
  getJSON(`${base}/actions.json`),
]);
setupHeader(cities, code, meta);
document.getElementById("ref-line").textContent =
  `Referência: ${meta.reference_date}. Fonte: ${meta.sources.map((s) => s.name).join("; ")}.`;
if (meta.demo) document.getElementById("map-chip").textContent = "Mapa ilustrativo · setores sintéticos";

const values = (p) => gj.features.map((f) => f.properties[p]).filter((v) => v != null);
const quantile = (arr, q) => {
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(q * s.length))];
};
for (const f of gj.features) {
  const p = f.properties;
  p.vuln = p.sensitivity != null && p.low_adaptation != null ? (p.sensitivity + p.low_adaptation) / 2 : null;
}
const median = (p) => quantile(values(p), 0.5);
const medians = { ndvi: median("ndvi"), exposure: median("exposure"), pop65: quantile(values("pop_65plus"), 0.75) };

function fillExpression(layer) {
  if (layer === "priority") {
    return ["match", ["get", "priority_class"], 0, CLASS_COLORS[0], 1, CLASS_COLORS[1], 2, CLASS_COLORS[2], 3, CLASS_COLORS[3], "#d8d2c2"];
  }
  const prop = LAYERS[layer].prop;
  const v = values(prop);
  const stops = [0.05, 0.35, 0.65, 0.95].map((q) => quantile(v, q));
  const ramp = RAMPS[layer];
  const expr = ["interpolate", ["linear"], ["to-number", ["get", prop], stops[0]]];
  stops.forEach((s, i) => {
    if (i === 0 || s > stops[i - 1]) expr.push(s, ramp[i]);
  });
  return ["case", ["==", ["get", prop], null], "#d8d2c2", expr];
}

function renderLegend(layer) {
  const box = document.getElementById("legend");
  box.replaceChildren();
  box.append(el("strong", { text: LAYERS[layer].title.split(" (")[0] }));
  if (layer === "priority") {
    CLASS_NAMES.forEach((n, i) => {
      const i_ = el("i");
      i_.style.background = CLASS_COLORS[i];
      box.append(el("span", {}, i_, n));
    });
  } else {
    const ramp = RAMPS[layer];
    const prop = LAYERS[layer].prop;
    const v = values(prop);
    [["menor", ramp[0]], ["", ramp[1]], ["", ramp[2]], ["maior", ramp[3]]].forEach(([t, c]) => {
      const i_ = el("i");
      i_.style.background = c;
      box.append(el("span", {}, i_, t));
    });
    const unit = layer === "heat" ? " °C" : "";
    box.append(el("span", { class: "small", text: `${fmt(quantile(v, 0.05), 2)}${unit} a ${fmt(quantile(v, 0.95), 2)}${unit}` }));
  }
}

const map = new maplibregl.Map({
  container: "map",
  style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#f1ecdd" } }] },
  bounds: meta.bounds,
  fitBoundsOptions: { padding: 30 },
  attributionControl: { compact: true },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

const equipFC = {
  type: "FeatureCollection",
  features: actions.cooling.map((e) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [e.lon, e.lat] },
    properties: { name: e.name, kind: e.kind, population: e.population, radius_m: e.radius_m },
  })),
};

let selectedId = null;

map.on("load", () => {
  map.addSource("sectors", { type: "geojson", data: gj, promoteId: "id" });
  map.addLayer({
    id: "fill",
    type: "fill",
    source: "sectors",
    paint: { "fill-color": fillExpression("priority"), "fill-opacity": 0.88 },
  });
  map.addLayer({
    id: "line",
    type: "line",
    source: "sectors",
    paint: {
      "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#0f3d22", "#fffdf8"],
      "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 0.7],
    },
  });
  map.addSource("equip", { type: "geojson", data: equipFC });
  map.addLayer({
    id: "equip",
    type: "circle",
    source: "equip",
    paint: {
      "circle-radius": 6,
      "circle-color": ["match", ["get", "kind"], "ubs", EQUIP_COLORS.ubs, "escola", EQUIP_COLORS.escola, EQUIP_COLORS.biblioteca],
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 2,
    },
  });
  renderLegend("priority");
  map.on("click", "fill", (e) => {
    if (map.queryRenderedFeatures(e.point, { layers: ["equip"] }).length) return;
    select(e.features[0].properties.id);
  });
  map.on("click", "equip", (e) => {
    e.originalEvent.stopPropagation?.();
    const p = e.features[0].properties;
    const box = el("div", {}, el("strong", { text: p.name }), el("br"),
      document.createTextNode(`${EQUIP_NAMES[p.kind] ?? p.kind} · cobre ${fmt(p.population)} pessoas em setores prioritários a ${p.radius_m} m`));
    new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(box).addTo(map);
  });
  for (const l of ["fill", "equip"]) {
    map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
  }
});

for (const r of document.querySelectorAll('input[name="layer"]')) {
  r.addEventListener("change", () => {
    map.setPaintProperty("fill", "fill-color", fillExpression(r.value));
    renderLegend(r.value);
  });
}
document.getElementById("equip").addEventListener("change", (e) => {
  map.setLayoutProperty("equip", "visibility", e.target.checked ? "visible" : "none");
});

function bar(label, value, color) {
  const fill = el("div", { class: "fill" });
  fill.style.width = `${Math.round((value ?? 0) * 100)}%`;
  fill.style.background = color;
  return el("div", { class: "bar" }, el("span", { text: label }), el("div", { class: "track", role: "img", "aria-label": `${label}: ${Math.round((value ?? 0) * 100)} de 100` }, fill));
}

function select(id) {
  const feat = gj.features.find((f) => f.properties.id === id);
  if (!feat) return false;
  const p = feat.properties;
  if (selectedId) map.setFeatureState({ source: "sectors", id: selectedId }, { selected: false });
  selectedId = id;
  map.setFeatureState({ source: "sectors", id }, { selected: true });

  document.getElementById("s-title").textContent = `Setor ${id}`;
  const body = document.getElementById("s-body");
  body.replaceChildren();
  const cls = p.priority_class;
  body.append(el("span", { class: `pill c${cls}`, text: cls >= 0 ? `Prioridade ${CLASS_NAMES[cls].toLowerCase()}` : "Sem dado" }));
  body.append(bar("Exposição ao calor", p.exposure, "#c8503c"));
  body.append(bar("Sensibilidade", p.sensitivity, "#ea8d45"));
  body.append(bar("Baixa capacidade de adaptação", p.low_adaptation, "#8dc63f"));

  body.append(el("h3", { text: "Por que investir aqui?", style: "margin-top:16px" }));
  const reasons = [];
  if (p.ndvi != null && p.ndvi <= medians.ndvi) reasons.push("Pouca cobertura vegetal");
  if (p.exposure != null && p.exposure >= 0.75) reasons.push("Maior exposição ao calor");
  if (p.pop_65plus != null && p.pop_65plus >= medians.pop65) reasons.push("Mais pessoas que precisam de proteção");
  const ul = el("ul", { class: "checks" });
  if (reasons.length === 0) ul.append(el("li", { class: "none", text: "Nenhum fator se destaca em relação à cidade" }));
  for (const r of reasons) ul.append(el("li", { text: r }));
  body.append(ul);
  body.append(el("p", { class: "small", text: `${fmt(p.population)} moradores (${fmt(p.pop_65plus)} com 65+) · anomalia de calor ${fmt(p.lst_anomaly_mean, 2)} °C · NDVI ${fmt(p.ndvi, 2)} · UBS a ${fmt(p.dist_ubs_m)} m` }));
  body.append(el("a", { class: "btn", href: `prioridades.html?cidade=${code}#arborizar`, text: "Ver ações recomendadas →" }));
  body.append(el("p", { class: "small", style: "margin-top:10px", text: `Fontes: ${meta.sources.map((s) => s.name).join(" · ")}. Referência: ${meta.reference_date}.` }));
  return true;
}

map.once("load", () => document.getElementById("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = document.getElementById("search").value.trim().toUpperCase();
  const feat = gj.features.find((f) => f.properties.id.toUpperCase() === q);
  if (!feat) {
    document.getElementById("search").setCustomValidity("Setor não encontrado");
    document.getElementById("search").reportValidity();
    return;
  }
  document.getElementById("search").setCustomValidity("");
  select(feat.properties.id);
  const pts = feat.geometry.coordinates.flat(feat.geometry.type === "MultiPolygon" ? 2 : 1);
  const b = new maplibregl.LngLatBounds(pts[0], pts[0]);
  for (const pt of pts) b.extend(pt);
  map.fitBounds(b, { padding: 80, maxZoom: 15 });
}));
document.getElementById("search").addEventListener("input", (e) => e.target.setCustomValidity(""));
