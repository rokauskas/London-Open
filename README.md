# DAX Momentum Burst Analysis

Project layout:

- `src/scripts/` - main scripts and modules
- `data/` - place CSV input files here (see `data/README.md`)
- `momentum_moves_charts/` - saved plots and generated images

## Quick Start

1. Place your CSV file in `data/` folder.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run with default (latest CSV in `data/`):
   ```
   python run.py
   ```
   Or specify an explicit path:
   ```
   python run.py --input /path/to/yourfile.csv --out momentum_moves_charts
   ```

## Output Files

- `bursts_main_*.png` - main tick chart with burst markers (green=longest, red=fastest)
- `burst_*_*.png` - zoomed views of each detected burst
- `bursts_summary.csv` - summary metrics for all bursts
- `burst_zscore_details.csv` - tick-by-tick Z-score breakdown within bursts

## Development

Code is under `src/` following modern Python packaging conventions. To make the package installable:
```
pip install -e .
```

Then run as a module:
```
python -m src.scripts.import_data_calc_delta_momentum --input data/yourfile.csv
```
