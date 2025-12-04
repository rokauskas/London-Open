# DAX Momentum - London Open Analysis

Advanced trading analysis tool for DAX futures during London Open session (08:00-10:00 UTC).

## Features

- **CSV Import**: Auto-detects and imports CSV files with OHLC + Volume data
- **London Open Focus**: Analyzes the critical 08:00-10:00 UTC timeframe
- **VWAP Calculation**: Volume-weighted average price from actual volume data
- **Session Average Analysis**: Tracks price behavior around session mean
- **ML Pattern Recognition**: Identifies high-quality patterns using machine learning
- **Quality Filtering**: Only saves patterns with strong follow-through
- **Detailed Visualizations**: ~10-15 high-quality charts per session
- **Telegram Integration**: Automatic notifications with chart and analysis
- **Candlestick Charts**: Proper OHLC visualization with timestamps

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

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Place CSV file in `var/input/`**
   - Required: OHLC + Volume data
   - Columns: `Local`, `Open`, `High`, `Low`, `Close`, `Volume`
   - Format: Second-level data recommended

4. **Configure Telegram (optional)**:
   ```bash
   cp etc/telegram_config.json.template etc/telegram_config.json
   # Edit with your bot_token and chat_id
   ```

5. **Run analysis**:
   ```bash
   python bin/analyze_london_open.py
   ```

## Usage

```bash
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

## Telegram Integration

Automatically sends after analysis:
- Chart image (VWAP + session avg)
- Session statistics

Setup:
1. Create bot with @BotFather
2. Get chat_id from `/getUpdates`
3. Add to `etc/telegram_config.json`

## Requirements

- Python 3.8+
- pandas >= 1.5
- numpy >= 1.24
- matplotlib >= 3.6
- mplfinance >= 0.12
- scikit-learn >= 1.0
- scipy >= 1.9
- requests >= 2.31

## License

MIT License
