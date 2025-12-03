# Place your CSV tick data files here

This folder holds the input CSV files for momentum burst analysis.

Example:
- `DEU.IDX-EUR_Tick_2025-11-14_09h_Local.csv`

Then run:
```
python run.py
```

Or specify a file explicitly:
```
python run.py --input /path/to/yourfile.csv --out momentum_moves_charts
```
