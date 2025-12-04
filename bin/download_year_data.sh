#!/bin/bash
# Download a full year of DAX data using Dukascopy
# Usage: ./bin/download_year_data.sh 2025

YEAR=${1:-2025}
OUTPUT_DIR="var/input/dukascopy"
TIMEFRAME="m5"

echo "Downloading DAX data for year $YEAR..."
echo "Output directory: $OUTPUT_DIR"
echo "Timeframe: $TIMEFRAME"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Download data month by month to avoid overwhelming the API
for month in {01..12}; do
    # Calculate the last day of the month
    if [ "$month" == "02" ]; then
        # Check for leap year
        if [ $((YEAR % 4)) -eq 0 ] && { [ $((YEAR % 100)) -ne 0 ] || [ $((YEAR % 400)) -eq 0 ]; }; then
            last_day=29
        else
            last_day=28
        fi
    elif [ "$month" == "04" ] || [ "$month" == "06" ] || [ "$month" == "09" ] || [ "$month" == "11" ]; then
        last_day=30
    else
        last_day=31
    fi
    
    from_date="${YEAR}-${month}-01"
    to_date="${YEAR}-${month}-${last_day}"
    output_file="${OUTPUT_DIR}/dax_${YEAR}_${month}.json"
    
    echo "Downloading $from_date to $to_date..."
    
    node bin/download_dukascopy_data.js \
        --from "$from_date" \
        --to "$to_date" \
        --timeframe "$TIMEFRAME" \
        --format json \
        --output "$output_file"
    
    if [ $? -eq 0 ]; then
        echo "✓ Saved to $output_file"
    else
        echo "✗ Failed to download data for $from_date to $to_date"
    fi
    
    echo ""
    
    # Small delay to be nice to the API
    sleep 2
done

echo "Year download complete!"
echo "Files saved in: $OUTPUT_DIR"
echo ""
echo "To merge all months into a single file, run:"
echo "  python bin/merge_dukascopy_data.py --input $OUTPUT_DIR --output var/input/dax_${YEAR}_full.csv"
