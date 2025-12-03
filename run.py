from pathlib import Path
import argparse
import sys


def main():
    p = argparse.ArgumentParser(description="Run momentum burst analysis on latest CSV or all CSVs in data/")
    p.add_argument("--input", "-i", type=Path, help="input CSV file (optional). If omitted, uses latest from data/")
    p.add_argument("--out", "-o", type=Path, default=Path("momentum_moves_charts"), help="output directory")
    p.add_argument("--all", action="store_true", help="process all CSVs in data/ instead of only latest")
    p.add_argument("--window", type=int, default=5)
    p.add_argument("--top", type=int, default=5)
    args = p.parse_args()

    data_dir = Path("data")
    
    if args.input:
        files = [args.input]
    else:
        # Only use data/ folder
        if not data_dir.exists():
            print(f"Error: {data_dir} folder does not exist.")
            sys.exit(1)
        
        csvs = list(data_dir.glob("*.csv"))
        
        if not csvs:
            print(f"No CSV files found in {data_dir}/")
            sys.exit(1)
        
        if args.all:
            files = sorted(csvs)
        else:
            files = [max(csvs, key=lambda p: p.stat().st_mtime)]

    # import the module-containing main function
    try:
        from src.scripts.import_data_calc_delta_momentum import main as analyze_main
    except Exception as e:
        print("Could not import module 'src.scripts.import_data_calc_delta_momentum'. Make sure you run this with the project root in PYTHONPATH, or install the package.")
        raise

    for f in files:
        print(f"Processing {f} -> {args.out}")
        analyze_main(Path(f), Path(args.out), window=args.window, top_n=args.top)


if __name__ == "__main__":
    main()
