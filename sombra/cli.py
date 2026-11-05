import argparse
import sys

from sombra.config import load_city, validate_ibge


def run_demo(ibge: str, out_dir=None) -> None:
    from sombra import pipeline
    from sombra.demo import build_demo
    from sombra.publish.export_web import export

    city = load_city(ibge)
    demo = build_demo(city)
    result = pipeline.run(
        city,
        demo.sector_ids,
        demo.geoms,
        demo.lst_anomaly,
        demo.transform,
        demo.census,
        demo.population,
        demo.equipment,
    )
    out = export(result, demo=True, reference_date="ilustrativo", out_dir=out_dir)
    ov = result.robustness["min_overlap"]
    print(f"{city.name}: {len(demo.geoms)} setores sintéticos -> {out}")
    print(f"sobreposição mínima do top 10% sob pesos alternativos: {ov:.0%}")


def lst_path(city, period: str):
    return city.processed_dir / f"lst_{period}.npz"


def run_lst(ibge: str, period: str) -> None:
    from sombra.ingest.ibge import RAW_IBGE, ensure_raw, load_sectors
    from sombra.ingest.landsat import (
        cache_params,
        composite_anomaly,
        save_composite,
        urban_mask_from,
    )

    city = load_city(ibge)
    files = ensure_raw(city.uf, RAW_IBGE)
    sectors = load_sectors(files["gpkg"], ibge)
    comp = composite_anomaly(
        city, recent_only=period == "recent", urban_mask_fn=urban_mask_from(sectors.geoms)
    )
    save_composite(comp, lst_path(city, period), cache_params(city, "lst", period))
    print(
        f"{city.name}: composto {period} com {len(comp.scenes)} datas -> {lst_path(city, period)}"
    )


def cached_equipment(city):
    import json

    from sombra.ingest.osm import fetch_equipment

    path = city.raw_dir / "osm_equipment.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fetch_equipment(city), ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def cached_ndvi(city):
    import numpy as np
    from rasterio.transform import Affine

    from sombra.ingest.landsat import cache_params, check_params
    from sombra.ingest.sentinel2 import median_ndvi

    path = city.processed_dir / "ndvi_recent.npz"
    params = cache_params(city, "ndvi")
    if not path.exists():
        arr, transform, dates = median_ndvi(city)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            params=np.array(params),
            ndvi=arr.astype("float32"),
            transform=np.array(transform)[:6],
            dates=np.array(dates),
        )
    z = np.load(path, allow_pickle=False)
    check_params(str(z["params"]) if "params" in z else "", params, path)
    return (
        z["ndvi"].astype("float64"),
        Affine(*[float(x) for x in z["transform"]]),
        [str(d) for d in z["dates"]],
    )


def run_real(ibge: str, period: str = "recent") -> None:
    import numpy as np
    from shapely.geometry import Point

    from sombra import pipeline
    from sombra.heat.zonal import zonal_stats
    from sombra.ingest.ibge import (
        CENSUS_REFERENCE,
        CENSUS_ZIPS,
        RAW_IBGE,
        ensure_raw,
        input_record,
        load_boundary_geom,
        load_sectors,
        read_census_zip,
        sectors_gpkg_url,
    )
    from sombra.ingest.landsat import cache_params, load_composite
    from sombra.publish.export_web import export
    from sombra.vulnerability.census import COR_RACA, DEMOGRAFIA, RENDA, census_indicators

    city = load_city(ibge)
    path = lst_path(city, period)
    if not path.exists():
        raise FileNotFoundError(f"{path} não existe; rode `sombra lst --city {ibge}` antes")
    files = ensure_raw(city.uf, RAW_IBGE)
    sectors = load_sectors(files["gpkg"], ibge)
    dem = read_census_zip(files["demografia"], ibge, DEMOGRAFIA)
    cor = read_census_zip(files["cor_raca"], ibge, COR_RACA)
    ren = read_census_zip(files["renda"], ibge, RENDA)
    census = census_indicators(sectors.ids, dem, cor, ren)
    census["persons_per_household"] = sectors.persons_per_household
    osm = cached_equipment(city)
    boundary = load_boundary_geom(ibge)
    equipment = [e for e in osm["equipment"] if boundary.contains(Point(e["lon"], e["lat"]))]
    # A distância à UBS só voltará ao índice com uma fonte oficial (CNES): as UBS do OSM
    # cobrem parte das unidades e inflariam a prioridade onde falta mapeamento.
    census["dist_ubs_m"] = np.full(len(sectors.ids), np.nan)
    ndvi_arr, ndvi_transform, ndvi_dates = cached_ndvi(city)
    census["ndvi"] = np.array(
        [z["mean"] for z in zonal_stats(ndvi_arr, ndvi_transform, sectors.geoms)]
    )
    comp = load_composite(path, cache_params(city, "lst", period))
    result = pipeline.run(
        city,
        sectors.ids,
        sectors.geoms,
        comp.anomaly,
        comp.transform,
        census,
        sectors.population,
        equipment,
    )
    result.notes = {
        "ndvi_scenes": ndvi_dates,
        "equipment": {
            k: sum(e["kind"] == k for e in equipment) for k in ("escola", "ubs", "biblioteca")
        },
        "osm_source": {"endpoint": osm["endpoint"], "base_timestamp": osm["osm_base"]},
        "ubs_source": "OpenStreetMap (nomes com UBS/USF/Unidade Básica); cobertura incompleta",
        "unavailable_indicators": ["dist_ubs_m"],
        "excluded_sectors": sectors.excluded,
        "included_sector_types": {t: sectors.types.count(t) for t in sorted(set(sectors.types))},
        "lst_scenes": comp.scenes,
        "lst_period": period,
        "census": CENSUS_REFERENCE,
        "inputs": [
            input_record(files["gpkg"], sectors_gpkg_url(city.uf)),
            *[input_record(files[k], CENSUS_ZIPS[k]) for k in CENSUS_ZIPS],
            input_record(city.raw_dir / "osm_equipment.json", "overpass (OpenStreetMap)"),
            input_record(path),
            input_record(city.processed_dir / "ndvi_recent.npz"),
        ],
    }
    out = export(
        result,
        demo=False,
        reference_date=(
            f"Censo 2022; Landsat {comp.scenes[0]} a {comp.scenes[-1]}; "
            f"Sentinel-2 {ndvi_dates[0]} a {ndvi_dates[-1]}; OSM {(osm['osm_base'] or '')[:10]}"
        ),
    )
    print(f"{city.name}: {len(sectors.ids)} setores reais -> {out}")
    overlap = result.robustness["min_overlap"]
    print(f"sobreposição mínima do top 10% sob pesos alternativos: {overlap:.0%}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sombra")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="roda o pipeline para um município")
    run.add_argument("--city", required=True, help="código IBGE de 7 dígitos")
    run.add_argument("--demo", action="store_true", help="usa a cidade sintética (sem rede)")
    run.add_argument("--out", help="pasta de saída (a demo nunca sobrescreve dados reais)")
    run.add_argument("--period", choices=["recent", "all"], default="recent")
    lst = sub.add_parser("lst", help="compõe e guarda a anomalia de calor de superfície (Landsat)")
    lst.add_argument("--city", required=True)
    lst.add_argument("--period", choices=["recent", "all"], default="recent")
    bnd = sub.add_parser("boundary", help="baixa o contorno oficial do município (IBGE)")
    bnd.add_argument("--city", required=True)
    args = parser.parse_args(argv)
    try:
        validate_ibge(args.city)
        if args.cmd == "lst":
            run_lst(args.city, args.period)
        elif args.cmd == "boundary":
            from sombra.ingest.ibge import fetch_boundary

            print(fetch_boundary(args.city, force=True))
        else:
            run_demo(args.city, args.out) if args.demo else run_real(args.city, args.period)
    except (ValueError, FileNotFoundError, NotImplementedError, RuntimeError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
