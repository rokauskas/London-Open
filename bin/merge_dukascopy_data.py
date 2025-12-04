#!/usr/bin/env python3
"""
Merge multiple Dukascopy data files into a single CSV file

Usage:
    python bin/merge_dukascopy_data.py --input var/input/dukascopy --output var/input/dax_2025_full.csv
    python bin/merge_dukascopy_data.py --input var/input/dukascopy --output var/input/dax_2025_full.json --format json
"""

import argparse
import json
from pathlib import Path
import pandas as pd


def merge_json_files(input_dir, output_file, format='csv'):
    """
    Merge multiple JSON files from Dukascopy into a single output file
    
    Args:
        input_dir (Path): Directory containing JSON files
        output_file (Path): Output file path
        format (str): Output format ('csv' or 'json')
    """
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        return
    
    # Find all JSON files
    json_files = sorted(input_path.glob("*.json"))
    
    if not json_files:
        print(f"Error: No JSON files found in {input_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files to merge")
    
    all_data = []
    
    for json_file in json_files:
        print(f"Reading {json_file.name}...")
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                all_data.extend(data)
            else:
                print(f"Warning: {json_file.name} does not contain a list")
        
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
            continue
    
    if not all_data:
        print("Error: No data to merge")
        return
    
    print(f"\nTotal records: {len(all_data)}")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data)
    
    # Sort by timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
    elif 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')
    
    # Remove duplicates
    initial_count = len(df)
    df = df.drop_duplicates()
    if len(df) < initial_count:
        print(f"Removed {initial_count - len(df)} duplicate records")
    
    # Create output directory if needed
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to output file
    if format.lower() == 'json':
        df.to_json(output_path, orient='records', date_format='iso', indent=2)
        print(f"\n✓ Merged data saved to {output_file} (JSON format)")
    else:
        df.to_csv(output_path, index=False)
        print(f"\n✓ Merged data saved to {output_file} (CSV format)")
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Total candles: {len(df)}")
    if 'timestamp' in df.columns:
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    elif 'time' in df.columns:
        print(f"  Date range: {df['time'].min()} to {df['time'].max()}")
    print(f"  Columns: {', '.join(df.columns)}")


def main():
    parser = argparse.ArgumentParser(
        description='Merge Dukascopy JSON data files into a single output file'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input directory containing JSON files'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output file path (CSV or JSON)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['csv', 'json'],
        default='csv',
        help='Output format (default: csv)'
    )
    
    args = parser.parse_args()
    
    merge_json_files(args.input, args.output, args.format)


if __name__ == '__main__':
    main()
