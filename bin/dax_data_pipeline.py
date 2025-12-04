#!/usr/bin/env python3
"""
DAX Data Download and MongoDB Storage

Downloads 5-minute DAX candle data from the previous session,
stores it in MongoDB, runs pattern analysis, and saves pattern URLs.

Security:
    - MongoDB credentials stored in etc/mongodb_config.json (gitignored)
    - Never hardcode credentials in source code
    - Use secure connection string with TLS

Usage:
    python bin/dax_data_pipeline.py
    python bin/dax_data_pipeline.py --date 2025-12-03
    python bin/dax_data_pipeline.py --analyze-only

Requirements:
    pip install pymongo yfinance pandas
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import json

# Add project root to Python path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import pandas as pd
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import ConnectionFailure, DuplicateKeyError
except ImportError:
    print("Error: Required packages not installed")
    print("Install with: pip install pymongo pandas")
    sys.exit(1)


def load_mongodb_config():
    """
    Load MongoDB configuration from secure config file
    
    Returns:
        dict: MongoDB configuration
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_path = project_root / "etc" / "mongodb_config.json"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"MongoDB config not found: {config_path}\n"
            f"Create it from mongodb_config.json.template"
        )
    
    with open(config_path) as f:
        config = json.load(f)
    
    if not config.get('connection_string'):
        raise ValueError("Missing 'connection_string' in MongoDB config")
    
    if not config.get('database'):
        raise ValueError("Missing 'database' in MongoDB config")
    
    return config


def get_mongodb_client(config):
    """
    Create MongoDB client with secure connection
    
    Args:
        config (dict): MongoDB configuration
    
    Returns:
        MongoClient: Connected MongoDB client
    
    Raises:
        ConnectionFailure: If connection fails
    """
    try:
        # Azure Cosmos DB for MongoDB requires longer timeouts
        client = MongoClient(
            config['connection_string'],
            serverSelectionTimeoutMS=30000,  # 30 seconds for Cosmos DB
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=False  # Cosmos DB requirement
        )
        
        # Test connection
        print("Testing MongoDB connection...")
        client.admin.command('ping')
        print(f"✓ Connected to MongoDB: {config['database']}")
        
        return client
    
    except ConnectionFailure as e:
        print(f"Error: Failed to connect to MongoDB: {e}")
        raise


def download_dax_data(date=None, interval='5m'):
    """
    Download DAX 5-minute candle data for specified date
    
    Args:
        date (str): Date in YYYY-MM-DD format (default: yesterday)
        interval (str): Candle interval (default: 5m)
    
    Returns:
        pd.DataFrame: OHLC data with columns [timestamp, open, high, low, close, volume]
    """
    try:
        import yfinance as yf
    except ImportError:
        print("Error: yfinance not installed. Install with: pip install yfinance")
        sys.exit(1)
    
    if date is None:
        # Default to yesterday
        target_date = datetime.now() - timedelta(days=1)
        date_str = target_date.strftime('%Y-%m-%d')
    else:
        date_str = date
        target_date = datetime.strptime(date, '%Y-%m-%d')
    
    print(f"\nDownloading DAX data for {date_str}...")
    
    # DAX ticker symbol
    ticker = "^GDAXI"
    
    # Download data for the specific day
    start_date = date_str
    end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=False
        )
        
        if df.empty:
            print(f"Warning: No data available for {date_str}")
            print("This might be a weekend or holiday. Try a different date.")
            return None
        
        # Reset index to get timestamp as column
        df = df.reset_index()
        
        # Rename columns to lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Rename 'datetime' to 'timestamp' if present
        if 'datetime' in df.columns:
            df = df.rename(columns={'datetime': 'timestamp'})
        
        print(f"✓ Downloaded {len(df)} candles")
        print(f"  Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        return df
    
    except Exception as e:
        print(f"Error downloading data: {e}")
        return None


def insert_ohlc_data(client, config, df, session_date):
    """
    Insert OHLC data into MongoDB
    
    Args:
        client (MongoClient): MongoDB client
        config (dict): MongoDB configuration
        df (pd.DataFrame): OHLC data
        session_date (str): Session date in YYYY-MM-DD format
    
    Returns:
        str: Session ID
    """
    db = client[config['database']]
    collection_name = config['collections']['ohlc_data']
    collection = db[collection_name]
    
    # Create index on timestamp and session_date for efficient queries
    collection.create_index([('session_date', ASCENDING), ('timestamp', ASCENDING)])
    collection.create_index([('timestamp', ASCENDING)])
    
    # Prepare documents
    session_id = f"dax_{session_date}"
    
    documents = []
    for _, row in df.iterrows():
        doc = {
            'session_id': session_id,
            'session_date': session_date,
            'timestamp': row['timestamp'],
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
            'inserted_at': datetime.utcnow()
        }
        documents.append(doc)
    
    print(f"\nInserting {len(documents)} candles into MongoDB...")
    
    try:
        # Insert documents
        result = collection.insert_many(documents, ordered=False)
        print(f"✓ Inserted {len(result.inserted_ids)} documents into '{collection_name}'")
        
    except DuplicateKeyError:
        # Some documents might already exist, insert individually
        inserted_count = 0
        for doc in documents:
            try:
                collection.insert_one(doc)
                inserted_count += 1
            except DuplicateKeyError:
                pass
        
        print(f"✓ Inserted {inserted_count} new documents (some already existed)")
    
    return session_id


def run_pattern_analysis(df, session_id, output_dir):
    """
    Run pattern analysis on OHLC data
    
    Args:
        df (pd.DataFrame): OHLC data
        session_id (str): Session identifier
        output_dir (Path): Output directory for pattern charts
    
    Returns:
        dict: Analysis results with pattern file paths
    """
    print(f"\n=== Running Pattern Analysis ===")
    
    # Import analysis modules
    from src.dax_momentum.analysis.ml_patterns import analyze_patterns
    from src.dax_momentum.analysis.pattern_visualizer import save_patterns_by_type
    
    # Ensure required columns exist
    if 'timestamp' in df.columns and 'Local' not in df.columns:
        df['Local'] = pd.to_datetime(df['timestamp'])
    
    # Rename columns to match expected format
    df.columns = [col.capitalize() if col.lower() in ['open', 'high', 'low', 'close', 'volume'] 
                  else col for col in df.columns]
    
    # Run ML pattern analysis
    pattern_results = analyze_patterns(df)
    
    # Create session-specific output directory
    session_output = output_dir / session_id
    session_output.mkdir(parents=True, exist_ok=True)
    
    # Generate pattern visualizations
    save_patterns_by_type(df, pattern_results, session_output)
    
    # Collect pattern file paths
    pattern_files = []
    patterns_dir = session_output / "patterns"
    
    if patterns_dir.exists():
        for pattern_file in patterns_dir.rglob("*.png"):
            pattern_files.append(str(pattern_file.relative_to(output_dir)))
    
    print(f"✓ Generated {len(pattern_files)} pattern charts")
    
    return {
        'session_id': session_id,
        'pattern_files': pattern_files,
        'metrics': pattern_results.get('metrics', {}),
        'cluster_count': len(pattern_results.get('cluster_summary', [])),
        'breakout_count': len(pattern_results.get('breakouts', [])),
        'anomaly_count': len(pattern_results.get('anomalies', [])),
        'swing_high_count': len(pattern_results.get('swing_highs', [])),
        'swing_low_count': len(pattern_results.get('swing_lows', []))
    }


def save_pattern_analysis(client, config, analysis_results):
    """
    Save pattern analysis results and file URLs to MongoDB
    
    Args:
        client (MongoClient): MongoDB client
        config (dict): MongoDB configuration
        analysis_results (dict): Pattern analysis results
    """
    db = client[config['database']]
    collection = db[config['collections']['pattern_analysis']]
    
    # Create index on session_id
    collection.create_index([('session_id', ASCENDING)])
    
    # Prepare document
    doc = {
        'session_id': analysis_results['session_id'],
        'pattern_count': len(analysis_results['pattern_files']),
        'pattern_files': analysis_results['pattern_files'],
        'metrics': analysis_results['metrics'],
        'cluster_count': analysis_results['cluster_count'],
        'breakout_count': analysis_results['breakout_count'],
        'anomaly_count': analysis_results['anomaly_count'],
        'swing_high_count': analysis_results['swing_high_count'],
        'swing_low_count': analysis_results['swing_low_count'],
        'analyzed_at': datetime.utcnow()
    }
    
    print(f"\nSaving pattern analysis to MongoDB...")
    
    # Upsert (update if exists, insert if not)
    result = collection.update_one(
        {'session_id': analysis_results['session_id']},
        {'$set': doc},
        upsert=True
    )
    
    if result.upserted_id:
        print(f"✓ Inserted pattern analysis document")
    else:
        print(f"✓ Updated existing pattern analysis document")


def save_session_summary(client, config, session_id, session_date, candle_count, analysis_results):
    """
    Save session summary to MongoDB
    
    Args:
        client (MongoClient): MongoDB client
        config (dict): MongoDB configuration
        session_id (str): Session identifier
        session_date (str): Session date
        candle_count (int): Number of candles
        analysis_results (dict): Pattern analysis results
    """
    db = client[config['database']]
    collection = db[config['collections']['session_summary']]
    
    # Create index
    collection.create_index([('session_date', ASCENDING)])
    
    doc = {
        'session_id': session_id,
        'session_date': session_date,
        'candle_count': candle_count,
        'pattern_count': len(analysis_results['pattern_files']),
        'processed_at': datetime.utcnow(),
        'status': 'completed'
    }
    
    collection.update_one(
        {'session_id': session_id},
        {'$set': doc},
        upsert=True
    )
    
    print(f"✓ Session summary saved")


def main():
    """Main pipeline function"""
    parser = argparse.ArgumentParser(
        description='Download DAX data, store in MongoDB, and analyze patterns'
    )
    parser.add_argument(
        '--date', '-d',
        type=str,
        help='Target date in YYYY-MM-DD format (default: yesterday)'
    )
    parser.add_argument(
        '--analyze-only', '-a',
        action='store_true',
        help='Only run analysis on existing data in database'
    )
    parser.add_argument(
        '--skip-analysis',
        action='store_true',
        help='Download and store data without running analysis'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip uncommitted changes check and proceed anyway'
    )
    
    args = parser.parse_args()
    
    # Check for uncommitted changes before proceeding
    if not args.force:
        from src.dax_momentum.git_utils import check_and_prompt_if_uncommitted
        if not check_and_prompt_if_uncommitted(project_root):
            sys.exit(0)
    
    # Determine session date
    if args.date:
        session_date = args.date
    else:
        session_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    session_id = f"dax_{session_date}"
    
    try:
        # Load MongoDB configuration
        print("Loading MongoDB configuration...")
        config = load_mongodb_config()
        
        # Connect to MongoDB
        client = get_mongodb_client(config)
        
        if not args.analyze_only:
            # Download DAX data
            df = download_dax_data(args.date)
            
            if df is None:
                print("Error: No data to process")
                return
            
            # Insert OHLC data into MongoDB
            session_id = insert_ohlc_data(client, config, df, session_date)
            
        else:
            # Load data from MongoDB for analysis
            print(f"\nLoading data from MongoDB for {session_date}...")
            db = client[config['database']]
            collection = db[config['collections']['ohlc_data']]
            
            cursor = collection.find({'session_date': session_date}).sort('timestamp', ASCENDING)
            documents = list(cursor)
            
            if not documents:
                print(f"Error: No data found in database for {session_date}")
                return
            
            df = pd.DataFrame(documents)
            print(f"✓ Loaded {len(df)} candles from database")
        
        if not args.skip_analysis:
            # Run pattern analysis
            output_dir = project_root / "var" / "output"
            analysis_results = run_pattern_analysis(df, session_id, output_dir)
            
            # Save pattern analysis to MongoDB
            save_pattern_analysis(client, config, analysis_results)
            
            # Save session summary
            save_session_summary(client, config, session_id, session_date, len(df), analysis_results)
            
            print(f"\n{'='*60}")
            print(f"✓ Pipeline completed successfully!")
            print(f"{'='*60}")
            print(f"Session ID: {session_id}")
            print(f"Candles: {len(df)}")
            print(f"Patterns: {len(analysis_results['pattern_files'])}")
            print(f"Output: var/output/{session_id}/patterns/")
            print(f"{'='*60}")
        else:
            print(f"\n✓ Data download and storage completed (analysis skipped)")
        
        # Close connection
        client.close()
        
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nSetup instructions:")
        print("1. Copy etc/mongodb_config.json.template to etc/mongodb_config.json")
        print("2. Add your MongoDB connection string and database name")
        print("3. Ensure the config file is gitignored (already configured)")
        sys.exit(1)
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
