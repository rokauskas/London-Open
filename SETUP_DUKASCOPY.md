# Dukascopy Data Setup Guide

This guide explains how to set up and use the Dukascopy data downloader for the DAX Momentum project.

## Why Dukascopy?

We switched from Alpha Vantage/yfinance to Dukascopy for several reasons:

1. **Higher Quality Data**: Professional-grade tick data from a Swiss forex bank
2. **Better Coverage**: More reliable historical data for DAX (Germany 40 Index)
3. **No API Keys**: Free access without registration or rate limits
4. **Multiple Timeframes**: Support for tick, second, minute, hour, and daily data
5. **Direct Access**: Download data directly without intermediary services

## Prerequisites

### 1. Node.js Installation

You need Node.js 18 or higher installed on your system.

**Check if Node.js is installed:**
```bash
node --version
npm --version
```

**If not installed, download from:**
- Official website: https://nodejs.org/
- Recommended: LTS (Long Term Support) version

### 2. Install Dependencies

**Python dependencies:**
```bash
pip install -r requirements.txt
```

**Node.js dependencies:**
```bash
npm install
```

This will install the `dukascopy-node` package and its dependencies.

## Quick Start

### Download Data for a Single Date

```bash
# Download 5-minute candles for January 2, 2025
node bin/download_dukascopy_data.js --date 2025-01-02 --timeframe m5 --output var/input/dax_20250102.json
```

### Download Data for a Date Range

```bash
# Download data for entire January 2025
node bin/download_dukascopy_data.js \
  --from 2025-01-01 \
  --to 2025-01-31 \
  --timeframe m5 \
  --output var/input/dax_jan_2025.json
```

### Download Full Year of Data

To download a full year, use the provided shell script that downloads month by month:

```bash
# Download all 2025 data (month by month)
./bin/download_year_data.sh 2025
```

This will:
- Download data for each month separately
- Save files to `var/input/dukascopy/`
- Add small delays between requests to be nice to the API

### Merge Monthly Files

After downloading monthly files, merge them into a single file:

```bash
# Merge into CSV
python bin/merge_dukascopy_data.py \
  --input var/input/dukascopy \
  --output var/input/dax_2025_full.csv

# Or merge into JSON
python bin/merge_dukascopy_data.py \
  --input var/input/dukascopy \
  --output var/input/dax_2025_full.json \
  --format json
```

## Using with Data Pipeline

The Python data pipeline automatically uses Dukascopy by default:

```bash
# Download and process data for a specific date
python bin/dax_data_pipeline.py --date 2025-01-02

# Download without analysis
python bin/dax_data_pipeline.py --date 2025-01-02 --skip-analysis

# Analyze existing data from MongoDB
python bin/dax_data_pipeline.py --date 2025-01-02 --analyze-only
```

The pipeline will:
1. Call the Node.js Dukascopy downloader
2. Parse the returned JSON data
3. Store in MongoDB (if configured)
4. Run pattern analysis
5. Generate visualizations

## Timeframe Options

The downloader supports various timeframes:

| Timeframe | Code | Use Case |
|-----------|------|----------|
| Tick data | `tick` | High-frequency analysis |
| 1 second | `s1` | Very short-term patterns |
| 1 minute | `m1` | Scalping strategies |
| 5 minutes | `m5` | **Default** - Intraday analysis |
| 15 minutes | `m15` | Medium-term patterns |
| 30 minutes | `m30` | Swing trading |
| 1 hour | `h1` | Position tracking |
| 4 hours | `h4` | Daily position analysis |
| 1 day | `d1` | Long-term analysis |

## Troubleshooting

### Error: "Node.js not found"

Make sure Node.js is installed and in your PATH:
```bash
which node  # Linux/Mac
where node  # Windows
```

### Error: "Cannot find module 'dukascopy-node'"

Install Node.js dependencies:
```bash
npm install
```

### Error: "No data available for this date"

This could mean:
- The date is a weekend or holiday (no trading)
- The date is in the future
- The date is before January 1, 2013 (Dukascopy's DAX data starts then)

Try a different date:
```bash
# Use a recent weekday
node bin/download_dukascopy_data.js --date 2024-12-02 --timeframe m5 --output test.json
```

### Error: Network/Connection Issues

If you see connection errors:
1. Check your internet connection
2. Verify you can access: https://datafeed.dukascopy.com/
3. Check if you're behind a proxy or firewall
4. Try again in a few minutes (temporary outage)

### Data Appears Empty

Some dates may have no trading activity. Try:
- Using a different date (recent weekday)
- Using a different timeframe
- Checking the date range is valid

## Data Format

### JSON Output

```json
[
  {
    "timestamp": "2025-01-02T08:00:00.000Z",
    "open": 19850.5,
    "high": 19855.2,
    "low": 19848.1,
    "close": 19852.3,
    "volume": 125
  },
  ...
]
```

### CSV Output

After merging with `merge_dukascopy_data.py`:

```csv
timestamp,open,high,low,close,volume
2025-01-02T08:00:00.000Z,19850.5,19855.2,19848.1,19852.3,125
...
```

## Advanced Usage

### Custom Instrument

To download other instruments (not just DAX):

```bash
# Bitcoin
node bin/download_dukascopy_data.js --date 2025-01-02 --instrument btcusd --output btc.json

# EUR/USD
node bin/download_dukascopy_data.js --date 2025-01-02 --instrument eurusd --output eurusd.json
```

See [dukascopy-node instruments](https://www.dukascopy-node.app/instruments) for full list.

### Output to stdout

Omit the `--output` parameter to print JSON to stdout:

```bash
node bin/download_dukascopy_data.js --date 2025-01-02 --timeframe m5 | jq .
```

## Integration with Existing Workflows

### Automated Daily Downloads

Create a cron job or scheduled task:

```bash
# Download yesterday's data every day at 1 AM
0 1 * * * cd /path/to/London-Open && node bin/download_dukascopy_data.js --date $(date -d yesterday +\%Y-\%m-\%d) --output var/input/daily/dax_$(date -d yesterday +\%Y\%m\%d).json
```

### Python Script Integration

The data pipeline already integrates Dukascopy. To use in your own Python scripts:

```python
import subprocess
import json
import pandas as pd

def download_dax_data(date_str):
    """Download DAX data using Dukascopy"""
    cmd = [
        'node', 'bin/download_dukascopy_data.js',
        '--date', date_str,
        '--timeframe', 'm5'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    
    return pd.DataFrame(data)

# Usage
df = download_dax_data('2025-01-02')
print(df.head())
```

## Support

- **Dukascopy Node Documentation**: https://www.dukascopy-node.app/
- **GitHub Repository**: https://github.com/Leo4815162342/dukascopy-node
- **Instrument List**: https://www.dukascopy-node.app/instruments

## Summary

1. Install Node.js 18+
2. Run `npm install`
3. Download data: `node bin/download_dukascopy_data.js --date YYYY-MM-DD`
4. For full year: `./bin/download_year_data.sh YYYY`
5. Merge files: `python bin/merge_dukascopy_data.py --input dir --output file.csv`
6. Use in pipeline: `python bin/dax_data_pipeline.py --date YYYY-MM-DD`

You're all set! The system will now use Dukascopy for high-quality DAX data.
