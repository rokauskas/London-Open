#!/bin/bash
# Test script for Dukascopy integration
# This script tests the Dukascopy downloader with a recent date

set -e  # Exit on error

echo "======================================"
echo "Dukascopy Integration Test"
echo "======================================"
echo ""

# Check Node.js
echo "1. Checking Node.js installation..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✓ Node.js version: $NODE_VERSION"
echo ""

# Check npm
echo "2. Checking npm installation..."
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo "✓ npm version: $NPM_VERSION"
echo ""

# Check dependencies
echo "3. Checking dukascopy-node installation..."
if [ ! -d "node_modules/dukascopy-node" ]; then
    echo "⚠ dukascopy-node not found, installing..."
    npm install
else
    echo "✓ dukascopy-node is installed"
fi
echo ""

# Test download with a recent date
echo "4. Testing data download..."
echo "Attempting to download data for a recent weekday..."
echo ""

# Calculate yesterday's date
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    YESTERDAY=$(date -v-1d +%Y-%m-%d)
else
    # Linux
    YESTERDAY=$(date -d yesterday +%Y-%m-%d)
fi

echo "Test date: $YESTERDAY"
echo ""

# Create test output directory
mkdir -p var/input/test

# Try to download data
TEST_OUTPUT="var/input/test/test_dax.json"

echo "Running: node bin/download_dukascopy_data.js --date $YESTERDAY --timeframe m5 --output $TEST_OUTPUT"
echo ""

if node bin/download_dukascopy_data.js --date "$YESTERDAY" --timeframe m5 --output "$TEST_OUTPUT"; then
    echo ""
    echo "✓ Download successful!"
    
    # Check file size
    if [ -f "$TEST_OUTPUT" ]; then
        FILE_SIZE=$(wc -c < "$TEST_OUTPUT")
        echo "✓ Output file created: $TEST_OUTPUT"
        echo "✓ File size: $FILE_SIZE bytes"
        
        # Count records
        if command -v jq &> /dev/null; then
            RECORD_COUNT=$(jq '. | length' "$TEST_OUTPUT")
            echo "✓ Records downloaded: $RECORD_COUNT"
        fi
        
        echo ""
        echo "======================================"
        echo "✓ All tests passed!"
        echo "======================================"
        echo ""
        echo "Next steps:"
        echo "1. Download full year: ./bin/download_year_data.sh 2025"
        echo "2. Merge data: python bin/merge_dukascopy_data.py --input var/input/dukascopy --output var/input/dax_2025.csv"
        echo "3. Run pipeline: python bin/dax_data_pipeline.py --date $YESTERDAY"
        echo ""
    else
        echo "❌ Output file was not created"
        exit 1
    fi
else
    echo ""
    echo "❌ Download failed!"
    echo ""
    echo "Possible reasons:"
    echo "- No internet connection"
    echo "- The date is a weekend/holiday (no trading data)"
    echo "- Dukascopy server is temporarily unavailable"
    echo ""
    echo "Try running manually with a known trading day (use a recent weekday):"
    echo "  node bin/download_dukascopy_data.js --date YYYY-MM-DD --timeframe m5 --output test.json"
    echo ""
    echo "Example for testing (adjust date to a recent weekday):"
    echo "  node bin/download_dukascopy_data.js --date $(date -d '2 weeks ago' +%Y-%m-%d 2>/dev/null || date -v-2w +%Y-%m-%d) --timeframe m5 --output test.json"
    exit 1
fi
