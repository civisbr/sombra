export const CLASS_COLORS = ["#f6e3a1", "#f2c066", "#ea8d45", "#c8503c"];
export const CLASS_NAMES = ["Menor", "Moderada", "Alta", "Muito alta"];

export function cityCode() {
  const q = new URLSearchParams(location.search).get("cidade");
  return q && /^\d{7}$/.test(q) ? q : null;
}

export async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export async function loadCities() {
  const cities = await getJSON("data/cities.json");
  const fallback = cities.find((c) => /^\d{7}$/.test(c.ibge));
  const asked = cityCode();
  const code = cities.some((c) => c.ibge === asked) ? asked : fallback?.ibge;
  if (!code) throw new Error("nenhuma cidade publicada");
  return { cities, code };
}

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

export function fmt(n, digits = 0) {
  return n == null ? "—" : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function setupHeader(cities, code, meta) {
  const sel = document.getElementById("city-select");
  for (const c of cities) {
    const o = el("option", { value: c.ibge, text: `${c.name}, ${c.uf}` });
    if (c.ibge === code) o.selected = true;
    sel.append(o);
  }
  sel.addEventListener("change", () => {
    location.search = `?cidade=${sel.value}`;
  });
  const dl = document.getElementById("download-link");
  dl.href = `dados.html?cidade=${code}`;
  for (const a of document.querySelectorAll("a[href*='.html']")) {
    const [path, hash] = a.getAttribute("href").split("#");
    a.href = `${path.split("?")[0]}?cidade=${code}${hash ? `#${hash}` : ""}`;
  }
  const badge = document.getElementById("demo-badge");
  if (badge) badge.hidden = !meta.demo;
}
