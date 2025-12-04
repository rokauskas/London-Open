# Migration Guide: From yfinance to Dukascopy

This guide helps you migrate from the old yfinance data source to the new Dukascopy integration.

## What Changed?

### Before (yfinance)
- Used Yahoo Finance API via `yfinance` Python package
- Limited to data available on Yahoo Finance
- Dependent on Yahoo Finance uptime and rate limits
- Required `yfinance>=0.2.30` package

### After (Dukascopy)
- Uses Dukascopy data via `dukascopy-node` Node.js package
- Professional-grade data from Swiss forex bank
- More reliable and consistent
- No API keys or rate limits
- Requires Node.js 18+

## Breaking Changes

### 1. Requirements

**Old:**
```bash
pip install yfinance
```

**New:**
```bash
# Python dependencies (yfinance now optional)
pip install -r requirements.txt

# Node.js dependencies (NEW)
npm install
```

### 2. Data Pipeline

The Python pipeline (`bin/dax_data_pipeline.py`) has been updated to use Dukascopy by default.

**No changes needed** if you use the pipeline normally:
```bash
# This now uses Dukascopy automatically
python bin/dax_data_pipeline.py --date 2025-01-02
```

**Fallback to yfinance** (if needed):
The old yfinance code is still available as a fallback, but you need to have yfinance installed:
```bash
pip install yfinance
```

### 3. Direct Data Download

**Old way (Python):**
```python
import yfinance as yf

df = yf.download("^GDAXI", start="2025-01-02", end="2025-01-03", interval="5m")
```

**New way (Node.js):**
```bash
node bin/download_dukascopy_data.js --date 2025-01-02 --timeframe m5 --output data.json
```

**New way (Python via subprocess):**
```python
import subprocess
import json
import pandas as pd

result = subprocess.run([
    'node', 'bin/download_dukascopy_data.js',
    '--date', '2025-01-02',
    '--timeframe', 'm5'
], capture_output=True, text=True)

data = json.loads(result.stdout)
df = pd.DataFrame(data)
```

## Step-by-Step Migration

### Step 1: Install Node.js

Download and install Node.js 18+ from https://nodejs.org/

Verify installation:
```bash
node --version  # Should be 18.0.0 or higher
npm --version
```

### Step 2: Install Node.js Dependencies

```bash
cd /path/to/London-Open
npm install
```

This installs the `dukascopy-node` package.

### Step 3: Test the Integration

Run the test script:
```bash
./bin/test_dukascopy.sh
```

Or manually test:
```bash
node bin/download_dukascopy_data.js --date 2024-12-02 --timeframe m5 --output test.json
```

### Step 4: Update Your Workflow

**If you use the data pipeline:**

No changes needed! The pipeline automatically uses Dukascopy:
```bash
python bin/dax_data_pipeline.py --date 2025-01-02
```

**If you download data manually:**

Replace yfinance calls with Dukascopy:
```bash
# Old
python -c "import yfinance as yf; yf.download(...)"

# New
node bin/download_dukascopy_data.js --date 2025-01-02 --output data.json
```

### Step 5: Download Historical Data

For a full year of data:
```bash
# Download all of 2025
./bin/download_year_data.sh 2025

# Merge into single file
python bin/merge_dukascopy_data.py \
  --input var/input/dukascopy \
  --output var/input/dax_2025_full.csv
```

## Common Migration Issues

### Issue 1: "Node.js not found"

**Solution:**
Install Node.js from https://nodejs.org/ and make sure it's in your PATH.

### Issue 2: "Cannot find module 'dukascopy-node'"

**Solution:**
```bash
npm install
```

### Issue 3: "I still want to use yfinance"

**Solution:**
You can still use yfinance if needed:

1. Install yfinance:
```bash
pip install yfinance
```

2. The pipeline has a fallback mode (though you'd need to modify the code to use it by default)

### Issue 4: "Data format is different"

**Solution:**
Both sources provide OHLC data with similar structure. The pipeline handles format conversion automatically.

Dukascopy format:
```json
{
  "timestamp": "2025-01-02T08:00:00.000Z",
  "open": 19850.5,
  "high": 19855.2,
  "low": 19848.1,
  "close": 19852.3,
  "volume": 0
}
```

Note: Volume may be 0 for some indices.

## Benefits of Migration

### 1. Better Data Quality
- Professional-grade tick data
- More reliable historical data
- Consistent timestamps

### 2. Better Coverage
- Data from 2013 for DAX
- Multiple timeframes (tick to daily)
- More instruments available

### 3. No Rate Limits
- No API keys needed
- No registration required
- No request throttling

### 4. More Flexibility
- Download tick data
- Various timeframes
- Multiple instruments (not just DAX)

## Comparison

| Feature | yfinance | Dukascopy |
|---------|----------|-----------|
| Setup | Python only | Python + Node.js |
| API Key | Not required | Not required |
| Rate Limits | Yes (Yahoo) | No |
| Data Quality | Good | Professional |
| Tick Data | No | Yes |
| Historical Depth | Limited | From 2013 |
| Instruments | Yahoo symbols | 800+ instruments |
| Cost | Free | Free |

## Rollback Plan

If you need to rollback to yfinance:

1. Install yfinance:
```bash
pip install yfinance
```

2. Modify `bin/dax_data_pipeline.py` line 108:
```python
# Change this:
def download_dax_data(date=None, interval='5m', use_dukascopy=True):

# To this:
def download_dax_data(date=None, interval='5m', use_dukascopy=False):
```

3. Continue using the pipeline normally

## Getting Help

- **Dukascopy Setup**: See `SETUP_DUKASCOPY.md`
- **Dukascopy Node Docs**: https://www.dukascopy-node.app/
- **GitHub Issues**: Report issues in the project repository

## Summary

1. ✅ Install Node.js 18+
2. ✅ Run `npm install`
3. ✅ Test with `./bin/test_dukascopy.sh`
4. ✅ Continue using the pipeline as before
5. ✅ Download historical data with `./bin/download_year_data.sh`

The migration is designed to be smooth - existing Python workflows continue to work with minimal changes!
