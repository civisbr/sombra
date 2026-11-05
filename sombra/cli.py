import argparse
import sys

from sombra.config import load_city, validate_ibge


def run_demo(ibge: str) -> None:
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
    out = export(result, demo=True, reference_date="ilustrativo")
    ov = result.robustness["min_overlap"]
    print(f"{city.name}: {len(demo.geoms)} setores sintéticos -> {out}")
    print(f"sobreposição mínima do top 10% sob pesos alternativos: {ov:.0%}")


def run_real(ibge: str) -> None:
    from sombra.ingest.ibge import fetch_sectors

    fetch_sectors(ibge)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sombra")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="roda o pipeline para um município")
    run.add_argument("--city", required=True, help="código IBGE de 7 dígitos")
    run.add_argument("--demo", action="store_true", help="usa a cidade sintética (sem rede)")
    bnd = sub.add_parser("boundary", help="baixa o contorno oficial do município (IBGE)")
    bnd.add_argument("--city", required=True)
    args = parser.parse_args(argv)
    try:
        validate_ibge(args.city)
        if args.cmd == "boundary":
            from sombra.ingest.ibge import fetch_boundary

            print(fetch_boundary(args.city, force=True))
        else:
            (run_demo if args.demo else run_real)(args.city)
    except (ValueError, FileNotFoundError, NotImplementedError, RuntimeError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
