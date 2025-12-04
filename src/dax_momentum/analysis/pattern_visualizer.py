"""
Pattern Visualization - Create detailed charts for each identified pattern
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from mplfinance.original_flavor import candlestick_ohlc
import matplotlib.dates as mdates
from pathlib import Path
import json
import os


def calculate_pattern_stats(pattern_df, context_window=30):
    """
    Calculate detailed statistics for a pattern occurrence
    """
    stats = {}
    
    # Price movement
    price_change = pattern_df['Close'].iloc[-1] - pattern_df['Open'].iloc[0]
    stats['move_pips'] = price_change * 10  # Convert to pips (0.1 point = 1 pip)
    stats['move_points'] = price_change
    
    # Speed calculation (pips per second)
    duration_seconds = len(pattern_df)
    stats['speed_pips_per_sec'] = abs(stats['move_pips'] / duration_seconds) if duration_seconds > 0 else 0
    
    # Reversal analysis - look ahead if possible
    if len(pattern_df) > context_window:
        peak_price = pattern_df['High'].max()
        trough_price = pattern_df['Low'].min()
        final_price = pattern_df['Close'].iloc[-1]
        
        # Calculate reversal from peak/trough
        if price_change > 0:  # Bullish move
            reversal = peak_price - final_price
            stats['reversal_pips'] = reversal * 10
            stats['reversal_pct'] = (reversal / peak_price) * 100 if peak_price != 0 else 0
        else:  # Bearish move
            reversal = final_price - trough_price
            stats['reversal_pips'] = reversal * 10
            stats['reversal_pct'] = (reversal / trough_price) * 100 if trough_price != 0 else 0
    else:
        stats['reversal_pips'] = 0
        stats['reversal_pct'] = 0
    
    # Volatility
    stats['volatility'] = pattern_df['Close'].std()
    stats['range_pips'] = (pattern_df['High'].max() - pattern_df['Low'].min()) * 10
    
    # Directional strength
    bullish = (pattern_df['Close'] > pattern_df['Open']).sum()
    bearish = (pattern_df['Close'] < pattern_df['Open']).sum()
    stats['directional_strength'] = abs(bullish - bearish) / len(pattern_df) * 100
    
    # Duration
    stats['duration_seconds'] = duration_seconds
    
    return stats


def send_pattern_to_telegram(pattern_name, pattern_idx, chart_path, stats):
    """
    Send pattern chart and metrics to Telegram immediately after creation.
    
    Args:
        pattern_name (str): Name of the pattern (e.g., "Bullish Breakout")
        pattern_idx (int): Index of the pattern in the dataframe
        chart_path (Path): Path to the saved chart image
        stats (dict): Pattern statistics dictionary
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # Load Telegram credentials
        config_path = Path(__file__).parent.parent.parent.parent / "etc" / "telegram_config.json"
        if not config_path.exists():
            return False
        
        with open(config_path) as f:
            config = json.load(f)
        
        bot_token = config.get('bot_token')
        chat_id = config.get('chat_id')
        
        if not bot_token or not chat_id:
            return False
        
        # Format caption with pattern metrics
        caption = f"""*{pattern_name} Pattern #{pattern_idx}*

📊 *Movement*
  • Move: {stats['move_pips']:+.1f} pips ({stats['move_points']:+.2f} pts)
  • Speed: {stats['speed_pips_per_sec']:.2f} pips/sec
  • Range: {stats['range_pips']:.1f} pips

🔄 *Reversal Analysis*
  • Reversal: {stats['reversal_pips']:.1f} pips
  • Reversal %: {stats['reversal_pct']:.2f}%

💪 *Strength Metrics*
  • Volatility: {stats['volatility']:.2f}
  • Directional: {stats['directional_strength']:.1f}%
  • Duration: {stats['duration_seconds']}s
"""
        
        # Send photo via Telegram
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        
        with open(chart_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            return True
            
    except Exception as e:
        print(f"  ⚠ Telegram send failed: {e}")
        return False


def plot_pattern_instance(df, pattern_name, pattern_idx, out_folder, context_before=30, context_after=30):
    """
    Plot a single pattern instance with context and statistics
    """
    # Validate index
    if pattern_idx >= len(df) or pattern_idx < 0:
        return None
    
    # Get context window
    start_idx = max(0, pattern_idx - context_before)
    end_idx = min(len(df), pattern_idx + context_after + 1)
    
    df_window = df.iloc[start_idx:end_idx].copy()
    
    if len(df_window) == 0 or pattern_idx >= len(df):
        return None
    
    df_pattern = df.iloc[pattern_idx:pattern_idx+1].copy()
    
    if len(df_pattern) == 0:
        return None
    
    # Calculate statistics
    stats = calculate_pattern_stats(df_window)
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    ax_main = fig.add_subplot(gs[0:2, :])
    ax_stats = fig.add_subplot(gs[2, 0])
    ax_volume = fig.add_subplot(gs[2, 1])
    
    # Main candlestick chart
    df_plot = df_window[["Local", "Open", "High", "Low", "Close"]].dropna()
    
    # Calculate appropriate candlestick width based on data density
    if len(df_plot) > 1:
        time_diff = (df_plot["Local"].iloc[-1] - df_plot["Local"].iloc[0]).total_seconds()
        width_factor = time_diff / len(df_plot) / 86400  # Convert to matplotlib date units
    else:
        width_factor = 1 / 86400
    
    df_plot["Date_num"] = mdates.date2num(df_plot["Local"])
    ohlc_data = df_plot[["Date_num", "Open", "High", "Low", "Close"]].values
    
    candlestick_ohlc(ax_main, ohlc_data, width=width_factor * 0.8, colorup='green', colordown='red', alpha=0.8)
    
    # Highlight pattern occurrence
    pattern_time = mdates.date2num(df_pattern["Local"].iloc[0])
    ax_main.axvline(x=pattern_time, color='orange', linestyle='--', linewidth=2, alpha=0.7, label='Pattern')
    
    # Format main chart
    ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax_main.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax_main.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    sf = ScalarFormatter(useMathText=False)
    sf.set_scientific(False)
    try:
        sf.set_useOffset(False)
    except Exception:
        pass
    ax_main.yaxis.set_major_formatter(sf)
    
    ax_main.set_title(f"{pattern_name} - Instance #{pattern_idx}", fontsize=14, fontweight='bold')
    ax_main.set_xlabel("Time", fontsize=12)
    ax_main.set_ylabel("Price", fontsize=12)
    ax_main.grid(True, alpha=0.3)
    ax_main.legend(fontsize=10)
    
    # Statistics panel
    ax_stats.axis('off')
    stats_text = f"""
PATTERN STATISTICS

Movement:
  • Move: {stats['move_pips']:+.1f} pips ({stats['move_points']:+.2f} pts)
  • Speed: {stats['speed_pips_per_sec']:.2f} pips/sec
  • Range: {stats['range_pips']:.1f} pips
  
Reversal Analysis:
  • Reversal: {stats['reversal_pips']:.1f} pips
  • Reversal %: {stats['reversal_pct']:.2f}%
  
Strength:
  • Volatility: {stats['volatility']:.2f}
  • Directional: {stats['directional_strength']:.1f}%
  • Duration: {stats['duration_seconds']}s
    """
    ax_stats.text(0.1, 0.5, stats_text, fontsize=11, family='monospace', 
                  verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    # Volume/momentum panel
    ax_volume.plot(df_window["Local"], df_window['Close'].pct_change() * 100, 
                   color='blue', linewidth=1.5, label='Returns %')
    ax_volume.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
    ax_volume.axvline(x=df_pattern["Local"].iloc[0], color='orange', linestyle='--', linewidth=2, alpha=0.7)
    ax_volume.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax_volume.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax_volume.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax_volume.set_xlabel("Time", fontsize=10)
    ax_volume.set_ylabel("Returns %", fontsize=10)
    ax_volume.grid(True, alpha=0.3)
    ax_volume.legend(fontsize=9)
    
    # Save figure
    out_folder.mkdir(parents=True, exist_ok=True)
    filename = f"pattern_{pattern_idx:04d}_{pattern_name.replace(' ', '_')}.png"
    filepath = out_folder / filename
    fig.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    # Send to Telegram immediately after creation
    if send_pattern_to_telegram(pattern_name, pattern_idx, filepath, stats):
        print(f"  ✓ Sent to Telegram: {pattern_name} #{pattern_idx}")
    
    return stats


def save_patterns_by_type(df, pattern_results, base_out_dir):
    """
    Save pattern instances into categorized folders with detailed visualizations.
    Only saves high-quality patterns that showed strong follow-through.
    """
    print("\n=== Generating High-Quality Pattern Visualizations ===")
    
    # 1. Save breakout patterns - only high-quality ones with strong follow-through
    if len(pattern_results['breakouts']) > 0:
        breakouts = pattern_results['breakouts']
        
        # Separate bullish and bearish
        bullish_breakouts = breakouts[breakouts['direction'] == 'bullish']
        bearish_breakouts = breakouts[breakouts['direction'] == 'bearish']
        
        # Filter bullish breakouts: must have strong continuation
        if len(bullish_breakouts) > 0:
            folder = base_out_dir / "patterns" / "bullish_breakouts"
            quality_breakouts = []
            
            for idx, row in bullish_breakouts.iterrows():
                # Check follow-through: price should continue up after breakout
                future_window = df.iloc[idx:min(idx+30, len(df))]  # Next 30 seconds
                if len(future_window) > 5:
                    price_change = future_window['Close'].iloc[-1] - future_window['Open'].iloc[0]
                    # Only keep if strong bullish follow-through (>3 points)
                    if price_change > 3.0:
                        stats = calculate_pattern_stats(future_window)
                        stats['index'] = idx
                        stats['quality_score'] = price_change * stats['speed_pips_per_sec']
                        quality_breakouts.append(stats)
            
            # Sort by quality score and keep top 3
            if quality_breakouts:
                quality_df = pd.DataFrame(quality_breakouts).sort_values('quality_score', ascending=False)
                print(f"\nGenerating {min(3, len(quality_df))} high-quality bullish breakout charts...")
                
                for i, (_, stats_row) in enumerate(quality_df.head(3).iterrows(), 1):
                    print(f"  [{i}/3] Creating chart...")
                    plot_pattern_instance(df, "Bullish Breakout", int(stats_row['index']), folder)
                
                quality_df.to_csv(folder / "summary_stats.csv", index=False)
        
        # Filter bearish breakouts: must have strong continuation
        if len(bearish_breakouts) > 0:
            folder = base_out_dir / "patterns" / "bearish_breakouts"
            quality_breakouts = []
            
            for idx, row in bearish_breakouts.iterrows():
                future_window = df.iloc[idx:min(idx+30, len(df))]
                if len(future_window) > 5:
                    price_change = future_window['Close'].iloc[-1] - future_window['Open'].iloc[0]
                    # Only keep if strong bearish follow-through (<-3 points)
                    if price_change < -3.0:
                        stats = calculate_pattern_stats(future_window)
                        stats['index'] = idx
                        stats['quality_score'] = abs(price_change) * stats['speed_pips_per_sec']
                        quality_breakouts.append(stats)
            
            if quality_breakouts:
                quality_df = pd.DataFrame(quality_breakouts).sort_values('quality_score', ascending=False)
                print(f"\nGenerating {min(3, len(quality_df))} high-quality bearish breakout charts...")
                
                for i, (_, stats_row) in enumerate(quality_df.head(3).iterrows(), 1):
                    print(f"  [{i}/3] Creating chart...")
                    plot_pattern_instance(df, "Bearish Breakout", int(stats_row['index']), folder)
                
                quality_df.to_csv(folder / "summary_stats.csv", index=False)
    
    # 2. Save anomaly patterns - only those with strong reversals
    if len(pattern_results['anomalies']) > 0:
        folder = base_out_dir / "patterns" / "anomalies"
        anomalies = pattern_results['anomalies']
        quality_anomalies = []
        
        for idx, row in anomalies.iterrows():
            # Look at behavior after anomaly - should show reversal
            future_window = df.iloc[idx:min(idx+60, len(df))]  # Next 60 seconds
            if len(future_window) > 10:
                stats = calculate_pattern_stats(future_window)
                # Good anomaly = high reversal power (mean reversion)
                if stats['reversal_pips'] > 30:  # At least 30 pips reversal
                    stats['index'] = idx
                    stats['quality_score'] = stats['reversal_pips'] / (stats['duration_seconds'] / 10)
                    quality_anomalies.append(stats)
        
        if quality_anomalies:
            quality_df = pd.DataFrame(quality_anomalies).sort_values('quality_score', ascending=False)
            limit = min(3, len(quality_df))
            print(f"\nGenerating {limit} high-quality anomaly charts...")
            
            for i, (_, stats_row) in enumerate(quality_df.head(3).iterrows(), 1):
                print(f"  [{i}/{limit}] Creating chart...")
                plot_pattern_instance(df, "Anomaly", int(stats_row['index']), folder)
            
            quality_df.to_csv(folder / "summary_stats.csv", index=False)
    
    # 3. Skip cluster patterns - too noisy, no clear quality signal
    
    # 4. Save swing points - only strongest with good follow-through
    swing_highs = pattern_results.get('swing_highs', [])
    swing_lows = pattern_results.get('swing_lows', [])
    
    if len(swing_highs) > 0:
        folder = base_out_dir / "patterns" / "swing_highs"
        quality_swings = []
        
        for idx in swing_highs:
            if idx < len(df) - 30:
                # Check if reversal happened after swing high
                future = df.iloc[idx:idx+30]
                price_drop = future['High'].iloc[0] - future['Low'].min()
                if price_drop > 10:  # At least 10 points drop
                    stats = calculate_pattern_stats(future)
                    stats['index'] = idx
                    stats['quality_score'] = price_drop
                    quality_swings.append(stats)
        
        if quality_swings:
            quality_df = pd.DataFrame(quality_swings).sort_values('quality_score', ascending=False)
            limit = min(3, len(quality_df))
            print(f"\nGenerating {limit} high-quality swing high charts...")
            
            for i, (_, stats_row) in enumerate(quality_df.head(3).iterrows(), 1):
                print(f"  [{i}/{limit}] Creating chart...")
                plot_pattern_instance(df, "Swing High", int(stats_row['index']), folder)
            
            quality_df.to_csv(folder / "summary_stats.csv", index=False)
    
    if len(swing_lows) > 0:
        folder = base_out_dir / "patterns" / "swing_lows"
        quality_swings = []
        
        for idx in swing_lows:
            if idx < len(df) - 30:
                # Check if reversal happened after swing low
                future = df.iloc[idx:idx+30]
                price_rise = future['High'].max() - future['Low'].iloc[0]
                if price_rise > 10:  # At least 10 points rise
                    stats = calculate_pattern_stats(future)
                    stats['index'] = idx
                    stats['quality_score'] = price_rise
                    quality_swings.append(stats)
        
        if quality_swings:
            quality_df = pd.DataFrame(quality_swings).sort_values('quality_score', ascending=False)
            limit = min(3, len(quality_df))
            print(f"\nGenerating {limit} high-quality swing low charts...")
            
            for i, (_, stats_row) in enumerate(quality_df.head(3).iterrows(), 1):
                print(f"  [{i}/{limit}] Creating chart...")
                plot_pattern_instance(df, "Swing Low", int(stats_row['index']), folder)
            
            quality_df.to_csv(folder / "summary_stats.csv", index=False)
    
    # 5. Save trend phase transitions - only large sustained moves
    if pattern_results.get('phases') is not None and len(pattern_results['phases']) > 0:
        phases = pattern_results['phases']
        
        # Find high-quality trend phases: large moves with good speed
        quality_phases = []
        for idx, phase in phases.iterrows():
            abs_change = abs(phase['price_change'])
            duration = phase.get('duration_seconds', phase.get('duration', 0))
            # Quality = large move (>15 points) with sustained pace
            if abs_change > 15 and duration > 20:  # Strong move over >20 seconds
                speed = abs_change / (duration / 10)  # Points per 10 seconds
                if speed > 3:  # Fast sustained move
                    phase['quality_score'] = abs_change * speed
                    quality_phases.append(phase)
        
        if quality_phases:
            quality_df = pd.DataFrame(quality_phases).sort_values('quality_score', ascending=False)
            folder = base_out_dir / "patterns" / "trend_transitions"
            folder.mkdir(parents=True, exist_ok=True)
            limit = min(3, len(quality_df))
            print(f"\nGenerating {limit} high-quality trend transition charts...")
            
            for i, (idx, phase) in enumerate(quality_df.head(3).iterrows(), 1):
                print(f"  [{i}/{limit}] Creating chart...")
                # Find approximate index in df
                phase_time = phase['start_time']
                df_idx = df[df['Local'] >= phase_time].index[0] if len(df[df['Local'] >= phase_time]) > 0 else 0
                
                stats = plot_pattern_instance(df, f"Trend Transition ({phase['trend']})", df_idx, folder)
                if stats:
                    stats['index'] = df_idx
                    stats['phase_trend'] = phase['trend']
            
            quality_df.to_csv(folder / "summary_stats.csv", index=False)
    
    print(f"\n✓ High-quality pattern visualizations saved to {base_out_dir}/patterns/")
