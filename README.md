# DAX Momentum - London Open Analysis

Advanced trading analysis tool for DAX futures during London Open session (08:00-10:00 UTC).

> **📚 New to Dukascopy?** See [SETUP_DUKASCOPY.md](SETUP_DUKASCOPY.md) for detailed setup instructions.  
> **🔄 Migrating from yfinance?** See [MIGRATION.md](MIGRATION.md) for migration guide.

## Features

- **Dukascopy Data Integration**: High-quality historical data via [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node)
- **CSV Import**: Auto-detects and imports CSV files with OHLC + Volume data
- **London Open Focus**: Analyzes the critical 08:00-10:00 UTC timeframe
- **VWAP Calculation**: Volume-weighted average price from actual volume data
- **Session Average Analysis**: Tracks price behavior around session mean
- **ML Pattern Recognition**: Identifies high-quality patterns using machine learning
- **Quality Filtering**: Only saves patterns with strong follow-through
- **Detailed Visualizations**: ~10-15 high-quality charts per session
- **Telegram Integration**: Automatic notifications with chart and analysis
- **Candlestick Charts**: Proper OHLC visualization with timestamps
- **MongoDB Storage**: Optional database integration for historical data management

## Project Structure

```
London-Open/
├── bin/                        # Executable scripts
│   ├── analyze_london_open.py # Main analysis script
│   └── send_telegram_notification.py  # Telegram notification script
├── etc/                        # Configuration files
│   ├── momentum_config.json   # Analysis settings
│   ├── telegram_config.json   # Telegram credentials (gitignored)
│   └── telegram_config.json.template  # Template
├── var/                        # Data and outputs
│   ├── input/                 # Input CSV files
│   └── output/                # Generated charts and analysis
│       ├── patterns/          # ML-detected patterns
│       └── price_chart_*.png
└── src/dax_momentum/          # Source code
    └── analysis/              # Analysis modules
```

## Quick Start

1. **Setup virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies** (for Dukascopy data downloader):
   ```bash
   npm install
   ```
   
   > **Note**: Node.js 18+ is required. Download from [nodejs.org](https://nodejs.org/)

4. **Download DAX data using Dukascopy**:
   ```bash
   # Download data for a specific date
   node bin/download_dukascopy_data.js --date 2025-01-02 --timeframe m5 --output var/input/dax_data.json
   
   # Download a full year (recommended)
   ./bin/download_year_data.sh 2025
   
   # Merge monthly files into one
   python bin/merge_dukascopy_data.py --input var/input/dukascopy --output var/input/dax_2025_full.csv
   ```

5. **Configure Telegram (optional)**:
   ```bash
   cp etc/telegram_config.json.template etc/telegram_config.json
   # Edit with your bot_token and chat_id
   ```

6. **Configure MongoDB (optional)**:
   ```bash
   cp etc/mongodb_config.json.template etc/mongodb_config.json
   # Edit with your connection_string and database name
   # Ensure your IP is whitelisted in Azure Cosmos DB firewall
   ```

7. **Run analysis**:
   ```bash
   python bin/analyze_london_open.py
   ```

## Usage

### Data Download (Dukascopy)

```bash
# Download data for a specific date
node bin/download_dukascopy_data.js --date 2025-01-02 --timeframe m5 --output var/input/dax_data.json

# Download a date range
node bin/download_dukascopy_data.js --from 2025-01-01 --to 2025-01-31 --timeframe m5 --output var/input/dax_jan.json

# Download full year (month by month)
./bin/download_year_data.sh 2025

# Merge monthly files
python bin/merge_dukascopy_data.py --input var/input/dukascopy --output var/input/dax_2025_full.csv
```

### Data Pipeline

```bash
# DAX Data Pipeline (download + MongoDB + analysis)
python bin/dax_data_pipeline.py --date 2025-12-03

# Download and store without analysis
python bin/dax_data_pipeline.py --skip-analysis

# Analyze existing data from MongoDB
python bin/dax_data_pipeline.py --analyze-only

# Run analysis on latest CSV
python bin/analyze_london_open.py

# Clean output before running
python bin/analyze_london_open.py --clean-output

# Send Telegram notification
python bin/send_telegram_notification.py
```

## Output

### Main Chart (`var/output/price_chart_*.png`)
- Candlestick chart with timestamps
- Session Average (blue dashed line)
- VWAP (orange solid line)
- 08:00-10:00 UTC timeframe

### Session Analysis (`session_average_analysis.json`)
```json
{
  "session_average": 23795.98,
  "vwap": 23785.18,
  "time_at_average_seconds": 112,
  "price_crosses": 76
}
```

### Pattern Charts (`patterns/{type}/`)
**Quality filters applied:**
- **Anomalies**: >30 pips mean-reversion
- **Swing Highs**: >10 points drop afterward
- **Swing Lows**: >10 points rise afterward
- **Trend Transitions**: >15 points, sustained speed

Each chart shows:
- Candlestick with 30s context
- Statistics panel
- Returns graph

## ML Pattern Recognition

### 1. Anomaly Detection (DBSCAN)
- Unusual price behavior detection
- **Filter**: >30 pips reversal
- Use: Reversal opportunities

### 2. Swing Points (scipy peaks)
- Local highs/lows identification
- **Filter**: >10 points reversal
- Use: Support/resistance levels

### 3. Trend Phases (EMA crossovers)
- Uptrend/Downtrend identification
- **Filter**: >15 points + fast speed
- Use: Trend-following entries

## Data Source

This project uses **[Dukascopy](https://www.dukascopy.com/)** as the primary data source via the [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) library.

### Why Dukascopy?

- **High Quality**: Professional-grade tick data from Swiss forex bank
- **Free Access**: No API keys or registration required
- **Historical Data**: Access to years of historical data
- **DAX Coverage**: Full support for Germany 40 Index (deuidxeur)
- **Multiple Timeframes**: From tick data to daily candles

### Supported Timeframes

- `tick` - Tick-by-tick data
- `s1` - 1 second
- `m1` - 1 minute
- `m5` - 5 minutes (default)
- `m15` - 15 minutes
- `m30` - 30 minutes
- `h1` - 1 hour
- `h4` - 4 hours
- `d1` - 1 day

### Instrument Information

- **Symbol**: `deuidxeur` (Germany 40 Index / DAX)
- **Type**: CFD Index
- **Data Available From**: January 1, 2013
- **Currency**: EUR

## Telegram Integration

Automatically sends after analysis:
- Chart image (VWAP + session avg)
- Session statistics

Setup:
1. Create bot with @BotFather
2. Get chat_id from `/getUpdates`
3. Add to `etc/telegram_config.json`

## Requirements

### Python Requirements
- Python 3.8+
- pandas >= 1.5
- numpy >= 1.24
- matplotlib >= 3.6
- mplfinance >= 0.12
- scikit-learn >= 1.0
- scipy >= 1.9
- requests >= 2.31
- pymongo >= 4.6

### Node.js Requirements
- Node.js 18+ ([Download](https://nodejs.org/))
- dukascopy-node (installed via `npm install`)

## Documentation

- **[SETUP_DUKASCOPY.md](SETUP_DUKASCOPY.md)** - Complete setup guide for Dukascopy data downloader
- **[MIGRATION.md](MIGRATION.md)** - Migration guide from yfinance to Dukascopy
- **[README.md](README.md)** - This file (project overview and quick start)

## Testing

Test the Dukascopy integration:
```bash
./bin/test_dukascopy.sh
```

## License

MIT License
