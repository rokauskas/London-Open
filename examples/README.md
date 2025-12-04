# Examples

This directory contains example scripts demonstrating how to use the DAX Momentum analysis tool.

## Available Examples

### 1. Download and Analyze (`download_and_analyze.sh`)

Complete workflow from data download to pattern analysis.

**Usage:**
```bash
# Analyze yesterday's data
./examples/download_and_analyze.sh

# Analyze a specific date
./examples/download_and_analyze.sh 2025-01-02
```

**What it does:**
1. Downloads DAX data from Dukascopy
2. Runs the data pipeline (stores in MongoDB if configured)
3. Performs pattern analysis
4. Generates visualizations
5. Shows summary of results

## Prerequisites

Before running examples:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   npm install
   ```

2. **Configure MongoDB (optional):**
   ```bash
   cp etc/mongodb_config.json.template etc/mongodb_config.json
   # Edit with your MongoDB credentials
   ```

3. **Configure Telegram (optional):**
   ```bash
   cp etc/telegram_config.json.template etc/telegram_config.json
   # Edit with your bot token and chat ID
   ```

## Creating Your Own Examples

You can create custom scripts based on these examples:

### Download Only

```bash
#!/bin/bash
# download_only.sh - Download data without analysis

DATE="2025-01-02"
node bin/download_dukascopy_data.js \
    --date "$DATE" \
    --timeframe m5 \
    --output "var/input/dax_${DATE}.json"
```

### Analyze Existing Data

```bash
#!/bin/bash
# analyze_only.sh - Analyze data already in MongoDB

DATE="2025-01-02"
python bin/dax_data_pipeline.py --date "$DATE" --analyze-only
```

### Download Year and Merge

```bash
#!/bin/bash
# download_year.sh - Download and merge full year

YEAR="2025"
./bin/download_year_data.sh "$YEAR"
python bin/merge_dukascopy_data.py \
    --input var/input/dukascopy \
    --output "var/input/dax_${YEAR}_full.csv"
```

## Troubleshooting

### Network Issues

If download fails with network errors:
- Check internet connection
- Verify Dukascopy is accessible: https://datafeed.dukascopy.com/
- Try a different date (weekday with trading activity)

### MongoDB Errors

If you see MongoDB connection errors:
- Ensure MongoDB is running and accessible
- Check `etc/mongodb_config.json` credentials
- Verify IP whitelist in Azure Cosmos DB (if using)
- Or run with `--skip-analysis` to skip MongoDB

### No Data for Date

If "No data available" message appears:
- The date might be a weekend or holiday
- Try a recent weekday
- Check date format is YYYY-MM-DD

## Next Steps

After running examples successfully:

1. **Customize analysis parameters** in `etc/momentum_config.json`
2. **Set up automated runs** using cron or Task Scheduler
3. **Integrate Telegram notifications** for real-time alerts
4. **Explore pattern analysis results** in `var/output/`

## Support

For more information, see:
- [Main README](../README.md)
- [Dukascopy Setup Guide](../SETUP_DUKASCOPY.md)
- [Migration Guide](../MIGRATION.md)
