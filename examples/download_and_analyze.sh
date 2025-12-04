#!/bin/bash
# Example: Download DAX data and run analysis
# This demonstrates the complete workflow from data download to pattern analysis

set -e  # Exit on error

echo "======================================"
echo "DAX Data Download and Analysis Example"
echo "======================================"
echo ""

# Configuration
DATE=${1:-$(date -d yesterday +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)}  # Default to yesterday
TIMEFRAME="m5"  # 5-minute candles
OUTPUT_DIR="var/input"
DATA_FILE="${OUTPUT_DIR}/dax_${DATE//-/}.json"

echo "Configuration:"
echo "  Date: $DATE"
echo "  Timeframe: $TIMEFRAME"
echo "  Output: $DATA_FILE"
echo ""

# Step 1: Download data
echo "Step 1: Downloading DAX data from Dukascopy..."
echo "----------------------------------------"

node bin/download_dukascopy_data.js \
    --date "$DATE" \
    --timeframe "$TIMEFRAME" \
    --output "$DATA_FILE"

if [ $? -ne 0 ]; then
    echo "❌ Failed to download data"
    exit 1
fi

echo ""
echo "✓ Data downloaded successfully"
echo ""

# Step 2: Run the data pipeline
echo "Step 2: Running data pipeline..."
echo "----------------------------------------"

python bin/dax_data_pipeline.py --date "$DATE"

if [ $? -ne 0 ]; then
    echo "❌ Pipeline failed"
    exit 1
fi

echo ""
echo "✓ Pipeline completed successfully"
echo ""

# Step 3: Show results
echo "Step 3: Results"
echo "----------------------------------------"

if [ -d "var/output/dax_${DATE}" ]; then
    echo "Output directory: var/output/dax_${DATE}"
    echo ""
    echo "Generated files:"
    find "var/output/dax_${DATE}" -type f | head -10
    echo ""
    
    # Count patterns
    PATTERN_COUNT=$(find "var/output/dax_${DATE}/patterns" -name "*.png" 2>/dev/null | wc -l)
    echo "Pattern charts generated: $PATTERN_COUNT"
else
    echo "⚠ No output directory created"
fi

echo ""
echo "======================================"
echo "✓ Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. View charts in var/output/dax_${DATE}/"
echo "2. Send Telegram notification: python bin/send_telegram_notification.py"
echo "3. View data in MongoDB (if configured)"
