# DAX Data Downloader Setup

## Node.js Setup (Required for Dukascopy)

### Install Node.js
1. Download Node.js from: https://nodejs.org/
2. Install the LTS version (includes npm)
3. Restart your terminal

### Verify Installation
```powershell
node --version
npm --version
```

## Install Dependencies
```powershell
cd D:\London-Open
npm install
```

This will install:
- `dukascopy-node`: Download historical forex/index data from Dukascopy
- `mongodb`: MongoDB driver for Node.js

## Usage

### Download a single date
```powershell
node bin/download_dax_dukascopy.js --date 2024-11-14
```

### Download a date range
```powershell
node bin/download_dax_dukascopy.js --start 2024-01-01 --end 2024-12-31
```

### Download full year
```powershell
node bin/download_dax_dukascopy.js --year 2024
```

### Download 2025 year-to-date
```powershell
node bin/download_dax_dukascopy.js --start 2025-01-01 --end 2025-12-04
```

## MongoDB Connection

The scripts use the MongoDB connection configured in `etc/mongodb_config.json`.

**Setup:** Copy the template and add your credentials:
```powershell
cp etc/mongodb_config.json.template etc/mongodb_config.json
# Edit etc/mongodb_config.json with your Azure Cosmos DB connection string
```

Database: `dax_trading`
Collections: `ohlc_5min`, `ohlc_1min`

## Data Schema

Each document contains:
- `timestamp`: Date/time of the candle
- `session_date`: Date string (YYYY-MM-DD)
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price
- `volume`: Trading volume
- `symbol`: "DE30EUR" (DAX)
- `interval`: "5m" (5 minutes)

## Features

✅ Downloads 5-minute OHLC candles from Dukascopy
✅ Automatically handles large date ranges (monthly chunks)
✅ Upserts data (no duplicates)
✅ Creates indexes for efficient querying
✅ Rate limiting to respect API limits
✅ Progress tracking with detailed logging

## Alternative: Use Python with yfinance

If you prefer to stay in Python without installing Node.js:

```powershell
python bin/download_historical_dax.py --year 2024
```

This uses Yahoo Finance instead of Dukascopy but may have rate limiting issues.

## Troubleshooting

### Node.js not found
Install Node.js from https://nodejs.org/ and restart terminal

### MongoDB connection timeout
Check your internet connection and MongoDB credentials

### No data for certain dates
Weekends and holidays have no trading data

### Rate limiting
The script automatically waits between chunks. For Yahoo Finance, add delays between requests.
