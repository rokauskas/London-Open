import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from mplfinance.original_flavor import candlestick_ohlc
import matplotlib.dates as mdates
from .ml_patterns import analyze_patterns
from .pattern_visualizer import save_patterns_by_type


def main(input_path: Path, out_dir: Path, window: int = 5, min_ticks: int = 1, gap_tolerance: int = 0,
         robust: bool = False, min_abs_change: float = 0.0, min_speed: float = 0.0, same_sign_count: int = 1):
    # Get project root for telegram script
    project_root = Path(__file__).parent.parent.parent
    
    # Clean old outputs before generating new ones
    import shutil
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read CSV
    df = pd.read_csv(input_path)
    
    # Parse time column robustly
    time_col = None
    for cand in ["Local", "Time", "Timestamp", "DateTime", "datetime", "time"]:
        if cand in df.columns:
            time_col = cand
            break
    if time_col is None:
        time_col = df.columns[0]
    
    df["Local"] = pd.to_datetime(df[time_col].astype(str).str.replace(r" UTC(\+\d{2}:\d{2})?$", "", regex=True), dayfirst=True, errors="coerce")
    if df["Local"].isna().all():
        df["Local"] = pd.to_datetime(df[time_col], dayfirst=True, errors="coerce")
    if df["Local"].isna().all():
        raise ValueError(f"Unable to parse datetime from column '{time_col}' in {input_path}")

    # Check for OHLC data
    has_ohlc = all(col in df.columns for col in ["Open", "High", "Low", "Close"])
    
    if has_ohlc:
        # Use OHLC data for candlestick chart
        df["Open"] = pd.to_numeric(df["Open"], errors="coerce")
        df["High"] = pd.to_numeric(df["High"], errors="coerce")
        df["Low"] = pd.to_numeric(df["Low"], errors="coerce")
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        
        # Calculate VWAP if volume data exists
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
            # VWAP = Cumulative(Typical Price * Volume) / Cumulative(Volume)
            df["TypicalPrice"] = (df["High"] + df["Low"] + df["Close"]) / 3
            df["TPV"] = df["TypicalPrice"] * df["Volume"]
            df["CumTPV"] = df["TPV"].cumsum()
            df["CumVolume"] = df["Volume"].cumsum()
            # Avoid division by zero
            df["VWAP"] = df["CumTPV"] / df["CumVolume"].replace(0, 1)
            print(f"Note: Plotting candlestick chart with VWAP from volume data")
        else:
            print(f"Note: Plotting candlestick chart from OHLC data (no volume for VWAP)")
    else:
        # Compute Mid price for line chart
        if "Mid" in df.columns:
            df["Mid"] = pd.to_numeric(df["Mid"], errors="coerce")
        elif "Ask" in df.columns and "Bid" in df.columns:
            df["Mid"] = (pd.to_numeric(df["Ask"], errors="coerce") + pd.to_numeric(df["Bid"], errors="coerce")) / 2
        elif "Close" in df.columns:
            df["Mid"] = pd.to_numeric(df["Close"], errors="coerce")
            print(f"Note: Using 'Close' price from OHLC data")
        elif "Last" in df.columns:
            df["Mid"] = pd.to_numeric(df["Last"], errors="coerce")
            print(f"Note: Using 'Last' price")
        else:
            raise ValueError("Missing price columns: expected 'Mid', 'Ask'/'Bid', 'Close' (OHLC), or 'Last'")

    # Filter to 08:00-10:00 UTC timeframe
    df = df.dropna(subset=["Local"])
    if len(df) > 0:
        # Extract time component and filter to 08:00-10:00 UTC
        df_time = df["Local"].dt.time
        start_time = pd.Timestamp('08:00:00').time()
        end_time = pd.Timestamp('10:00:00').time()
        df = df[(df_time >= start_time) & (df_time <= end_time)]
        
        if len(df) > 0:
            print(f"Filtered to London Open timeframe: 08:00-10:00 UTC")
            
            # Calculate insights for this timeframe
            if has_ohlc:
                price_range = df["High"].max() - df["Low"].min()
                open_price = df["Open"].iloc[0]
                close_price = df["Close"].iloc[-1]
                price_change = close_price - open_price
                price_change_pct = (price_change / open_price) * 100
                
                print(f"\n=== London Open Analysis (08:00-10:00 UTC) ===")
                print(f"Open:  {open_price:.2f}")
                print(f"Close: {close_price:.2f}")
                print(f"High:  {df['High'].max():.2f}")
                print(f"Low:   {df['Low'].min():.2f}")
                print(f"Range: {price_range:.2f} points")
                print(f"Change: {price_change:+.2f} ({price_change_pct:+.2f}%)")
                print(f"Total candles: {len(df)}")
                
                # Calculate session average and time at average price
                session_avg = df['Close'].mean()
                
                # Calculate proper VWAP from volume data if available
                if 'VWAP' in df.columns and not df['VWAP'].isna().all():
                    vwap = df['VWAP'].iloc[-1]  # Use final cumulative VWAP
                else:
                    vwap = ((df['High'] + df['Low'] + df['Close']) / 3).mean()  # Fallback to simple average
                
                # Calculate time spent near average price (within ±0.5 points tolerance)
                tolerance = 0.5
                near_avg = df[(df['Close'] >= session_avg - tolerance) & (df['Close'] <= session_avg + tolerance)]
                time_at_avg_seconds = len(near_avg)
                time_at_avg_minutes = time_at_avg_seconds / 60
                time_at_avg_pct = (time_at_avg_seconds / len(df)) * 100
                
                # Count how many times price crossed the average
                crosses = ((df['Close'].shift(1) < session_avg) & (df['Close'] >= session_avg)) | \
                         ((df['Close'].shift(1) > session_avg) & (df['Close'] <= session_avg))
                num_crosses = crosses.sum()
                
                print(f"\n=== Session Average Price Analysis ===")
                print(f"Session Average (Mean): {session_avg:.2f}")
                print(f"VWAP (Volume-Weighted): {vwap:.2f}")
                print(f"Time at Average (±{tolerance} pts):")
                print(f"  • Duration: {time_at_avg_seconds}s ({time_at_avg_minutes:.1f} min)")
                print(f"  • Percentage: {time_at_avg_pct:.2f}% of session")
                print(f"  • Price crosses: {num_crosses} times")
                
                # Save average price analysis
                avg_analysis = {
                    'session_average': float(session_avg),
                    'vwap': float(vwap),
                    'time_at_avg_seconds': int(time_at_avg_seconds),
                    'time_at_avg_minutes': float(time_at_avg_minutes),
                    'time_at_avg_pct': float(time_at_avg_pct),
                    'price_crosses': int(num_crosses),
                    'tolerance_points': float(tolerance)
                }
                import json
                avg_file = out_dir / "session_average_analysis.json"
                with open(avg_file, 'w') as f:
                    json.dump(avg_analysis, f, indent=2)
                
                # Send Telegram notification
                try:
                    import subprocess
                    telegram_script = project_root / "bin" / "telegram_post"
                    result = subprocess.run(
                        ["python", str(telegram_script)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        print("✓ Telegram notification sent")
                    else:
                        print(f"Note: Telegram notification failed - {result.stderr}")
                except Exception as e:
                    print(f"Note: Telegram notification not sent - {e}")
                
                # Run ML pattern analysis
                pattern_results = analyze_patterns(df)
                
                # Save pattern analysis results
                if pattern_results['cluster_summary'] is not None:
                    cluster_file = out_dir / "cluster_summary.csv"
                    pattern_results['cluster_summary'].to_csv(cluster_file, index=False)
                
                if len(pattern_results['breakouts']) > 0:
                    breakout_file = out_dir / "breakouts.csv"
                    pattern_results['breakouts'].to_csv(breakout_file, index=False)
                
                if len(pattern_results['anomalies']) > 0:
                    anomaly_file = out_dir / "anomalies.csv"
                    pattern_results['anomalies'].to_csv(anomaly_file, index=False)
                
                if pattern_results['phases'] is not None and len(pattern_results['phases']) > 0:
                    phases_file = out_dir / "trend_phases.csv"
                    pattern_results['phases'].to_csv(phases_file, index=False)
                
                print(f"\nPattern analysis results saved to {out_dir}/")
                
                # Generate detailed pattern visualizations
                save_patterns_by_type(df, pattern_results, out_dir)
        else:
            print("Warning: No data found in 08:00-10:00 UTC timeframe")

    # Plot chart
    fig, ax = plt.subplots(figsize=(14, 7))
    
    if has_ohlc and len(df) > 0:
        # Prepare data for candlestick chart
        df_plot = df[["Local", "Open", "High", "Low", "Close"]].dropna()
        df_plot["Date_num"] = mdates.date2num(df_plot["Local"])
        ohlc_data = df_plot[["Date_num", "Open", "High", "Low", "Close"]].values
        
        # Plot candlesticks
        candlestick_ohlc(ax, ohlc_data, width=0.0003, colorup='green', colordown='red', alpha=0.8)
        
        # Add session average line
        session_avg = df['Close'].mean()
        ax.axhline(y=session_avg, color='blue', linestyle='--', linewidth=2, alpha=0.7, label=f'Session Avg: {session_avg:.2f}')
        
        # Add VWAP line if available
        if 'VWAP' in df.columns and not df['VWAP'].isna().all():
            ax.plot(df_plot['Local'], df['VWAP'].loc[df_plot.index], color='orange', linestyle='-', linewidth=2, alpha=0.8, label=f'VWAP: {df["VWAP"].iloc[-1]:.2f}')
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    else:
        # Plot line chart
        if len(df) > 0:
            ax.plot(df["Local"], df["Mid"], color="gray", label="Mid Price", linewidth=1)
            session_avg = df["Mid"].mean()
            ax.axhline(y=session_avg, color='blue', linestyle='--', linewidth=2, alpha=0.7, label=f'Session Avg: {session_avg:.2f}')
        ax.legend()
    
    # Format y-axis to show full prices
    sf = ScalarFormatter(useMathText=False)
    sf.set_scientific(False)
    try:
        sf.set_useOffset(False)
    except Exception:
        pass
    ax.yaxis.set_major_formatter(sf)
    
    chart_type = "Candlestick Chart" if has_ohlc else "Price Chart"
    ax.set_title(f"{chart_type}: {input_path.stem} (London Open 08:00-10:00 UTC)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    fig.autofmt_xdate()

    # Save chart
    main_fname = f"price_chart_{input_path.stem}.png"
    main_out_path = out_dir / main_fname
    try:
        fig.savefig(main_out_path, dpi=150)
        print(f"Saved chart: {main_fname}")
    except Exception as e:
        print(f"Error saving chart: {e}")
    finally:
        plt.close(fig)
    time_col = None

