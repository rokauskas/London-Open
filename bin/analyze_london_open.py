#!/usr/bin/env python3
"""
London Open Analysis - Main Entry Point

Analyzes DAX futures during the London Open session (08:00-10:00 UTC) using:
- OHLC candlestick charts with VWAP
- Session average price analysis
- ML-based pattern recognition (anomalies, swings, trends)
- Quality filtering for high-probability patterns
- Telegram notifications with results

Usage:
    python bin/analyze_london_open.py [--clean-output]
    python bin/analyze_london_open.py --input var/input/yourfile.csv

Example:
    python bin/analyze_london_open.py --clean-output
    python bin/send_telegram_notification.py
"""
import sys
from pathlib import Path
import argparse
import json
import shutil

# Add project root to Python path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    """
    Main analysis orchestration function.
    
    Performs the following steps:
    1. Loads configuration from etc/momentum_config.json
    2. Discovers CSV files in var/input/ directory
    3. Runs analysis pipeline for each file:
       - Parses OHLC + Volume data
       - Filters to London Open timeframe (08:00-10:00 UTC)
       - Calculates VWAP and session averages
       - Detects ML patterns with quality filters
       - Generates visualizations
       - Sends Telegram notifications
    4. Saves outputs to var/output/ directory
    
    Command-line arguments override config file settings.
    """
    # Load defaults from optional config file if present
    config_path = Path("etc/momentum_config.json")
    # Fallback to root for backward compatibility
    if not config_path.exists():
        config_path = Path("momentum_config.json")
    config_defaults = {}
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as fh:
                config_defaults = json.load(fh)
        except Exception:
            config_defaults = {}

    def cfg(key, default):
        return config_defaults.get(key, default)

    p = argparse.ArgumentParser(description="Run momentum burst analysis on latest CSV or all CSVs in data/")
    p.add_argument("--input", "-i", type=Path, help="input CSV file (optional). If omitted, uses config or latest from data_dir")
    p.add_argument("--out", "-o", type=Path, default=Path("var") / cfg("out", "output"), help="output directory")
    p.add_argument("--all", action="store_true", help="process all CSVs in data_dir instead of only latest")
    p.add_argument("--clean-output", action="store_true", help="clear entire output directory before writing results")
    p.add_argument("--force", "-f", action="store_true", help="skip uncommitted changes check and proceed anyway")
    p.add_argument("--window", type=int, default=cfg("window", 5))
    p.add_argument("--min", type=int, default=cfg("min_ticks", 1), help="minimum ticks in a burst (default=1)")
    p.add_argument("--gap", type=int, default=cfg("gap", 0), help="maximum gap (ticks) between burst runs to merge them")
    p.add_argument("--robust", action="store_true", default=cfg("robust", False), help="use robust z-score (median/MAD) instead of mean/std")
    p.add_argument("--min-abs", type=float, default=cfg("min_abs", 0.0), help="minimum absolute price change for a burst (price units)")
    p.add_argument("--min-speed", type=float, default=cfg("min_speed", 0.0), help="minimum speed (price/sec) for a burst")
    p.add_argument("--same-sign", type=int, default=cfg("same_sign", 1), help="minimum number of same-sign ticks inside burst")
    args = p.parse_args()

    # Check for uncommitted changes before proceeding
    if not args.force:
        from src.dax_momentum.git_utils import check_and_prompt_if_uncommitted
        if not check_and_prompt_if_uncommitted(project_root):
            sys.exit(0)

    # Get data directory from config
    data_dir = Path(cfg("data_dir", "var/input"))
    
    # Clean output directory if requested
    if args.clean_output and args.out.exists():
        try:
            shutil.rmtree(args.out)
            print(f"Cleared output directory: {args.out}")
        except Exception as e:
            print(f"Warning: could not clear output directory {args.out}: {e}")
    
    if args.input:
        # If a directory is provided, process all CSVs within it (or latest if not --all)
        if args.input.is_dir():
            csvs = sorted(args.input.glob("*.csv"))
            if not csvs:
                print(f"No CSV files found in {args.input}/")
                sys.exit(1)
            files = csvs if args.all else [max(csvs, key=lambda p: p.stat().st_mtime)]
        else:
            # Any filename is accepted as long as it ends with .csv
            if args.input.suffix.lower() != ".csv":
                print(f"Error: --input must be a .csv file or a directory containing .csv files: {args.input}")
                sys.exit(1)
            files = [args.input]
    else:
        # No input specified: search for CSVs in data_dir first, then current directory
        csvs = []
        
        # Priority 1: Look in data_dir (make it absolute from project root)
        abs_data_dir = project_root / data_dir
        if abs_data_dir.exists() and abs_data_dir.is_dir():
            data_csvs = list(abs_data_dir.glob("*.csv"))
            if data_csvs:
                csvs = data_csvs
                print(f"Found {len(csvs)} CSV file(s) in {data_dir}/")
        
        # Priority 2: If no files in data_dir, check current working directory
        if not csvs:
            cwd = Path.cwd()
            cwd_csvs = list(cwd.glob("*.csv"))
            if cwd_csvs:
                csvs = cwd_csvs
                print(f"No CSV files in {data_dir}/, using files from current directory")
        
        if not csvs:
            print(f"No CSV files found in 'var/input/' or current directory")
            print(f"\nPlease either:")
            print(f"  1. Place a CSV file in 'var/input/' directory")
            print(f"  2. Specify a file with --input <path>")
            sys.exit(1)
        
        # Use all CSVs if --all flag, otherwise use the most recent one
        if args.all:
            files = sorted(csvs)
            print(f"Processing {len(files)} CSV file(s)")
        else:
            files = [max(csvs, key=lambda p: p.stat().st_mtime)]
            print(f"Using most recent CSV: {files[0].name}")

    # Import the analysis module
    from src.dax_momentum.analysis.burst_detector import main as analyze_main

    for f in files:
        print(f"Processing {f} -> {args.out}")
        analyze_main(Path(f), Path(args.out), window=args.window, min_ticks=args.min, gap_tolerance=args.gap,
                 robust=args.robust, min_abs_change=args.min_abs, min_speed=args.min_speed, same_sign_count=args.same_sign)


if __name__ == "__main__":
    main()
