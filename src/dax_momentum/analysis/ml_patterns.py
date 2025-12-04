"""
Machine Learning Pattern Recognition for London Open Trading Data
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy.stats import zscore
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')


def engineer_features(df):
    """
    Engineer features for ML pattern detection
    """
    features = pd.DataFrame()
    
    # Basic price features
    features['body'] = df['Close'] - df['Open']
    features['body_pct'] = (features['body'] / df['Open']) * 100
    features['range'] = df['High'] - df['Low']
    features['upper_shadow'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    features['lower_shadow'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    features['is_bullish'] = (df['Close'] > df['Open']).astype(int)
    
    # Momentum features
    features['price_momentum'] = df['Close'].diff()
    features['price_acceleration'] = features['price_momentum'].diff()
    features['volume_price_trend'] = features['body'] * df.get('Volume', 1)
    
    # Rolling statistics (5-second windows)
    features['volatility_5s'] = df['Close'].rolling(5).std()
    features['momentum_5s'] = df['Close'].pct_change(5)
    features['range_5s'] = df['High'].rolling(5).max() - df['Low'].rolling(5).min()
    
    # Rolling statistics (30-second windows)
    features['volatility_30s'] = df['Close'].rolling(30).std()
    features['momentum_30s'] = df['Close'].pct_change(30)
    features['range_30s'] = df['High'].rolling(30).max() - df['Low'].rolling(30).min()
    
    # Trend indicators
    features['sma_10'] = df['Close'].rolling(10).mean()
    features['distance_from_sma'] = df['Close'] - features['sma_10']
    features['price_position'] = (df['Close'] - df['Low'].rolling(30).min()) / (df['High'].rolling(30).max() - df['Low'].rolling(30).min())
    
    return features.fillna(0)


def detect_swing_points(df, prominence=0.5):
    """
    Detect swing highs and lows using peak detection
    """
    highs, _ = find_peaks(df['High'].values, prominence=prominence)
    lows, _ = find_peaks(-df['Low'].values, prominence=prominence)
    
    return highs, lows


def identify_breakout_patterns(df, threshold=2.0):
    """
    Identify price breakout patterns using z-score
    """
    df = df.copy()
    df['price_zscore'] = zscore(df['Close'])
    df['volume_zscore'] = zscore(df.get('Volume', pd.Series([1]*len(df))))
    
    # Breakout: significant price move with high volume
    breakouts = df[
        (abs(df['price_zscore']) > threshold) & 
        (df['volume_zscore'] > 1.0)
    ].copy()
    
    breakouts['direction'] = np.where(breakouts['price_zscore'] > 0, 'bullish', 'bearish')
    
    return breakouts


def cluster_price_behavior(df, n_clusters=5):
    """
    Cluster similar price behaviors using K-Means
    """
    features = engineer_features(df)
    
    # Select key features for clustering
    cluster_features = features[[
        'body_pct', 'range', 'volatility_30s', 'momentum_30s', 'price_position'
    ]].copy()
    
    # Standardize features
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(cluster_features)
    
    # Apply K-Means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(scaled_features)
    
    # Characterize each cluster
    cluster_summary = []
    for i in range(n_clusters):
        cluster_data = df[df['cluster'] == i]
        summary = {
            'cluster': i,
            'count': len(cluster_data),
            'avg_body': cluster_data['Close'].sub(cluster_data['Open']).mean(),
            'avg_range': (cluster_data['High'] - cluster_data['Low']).mean(),
            'bullish_pct': (cluster_data['Close'] > cluster_data['Open']).mean() * 100,
            'avg_volatility': cluster_data['Close'].std(),
        }
        cluster_summary.append(summary)
    
    return df, pd.DataFrame(cluster_summary)


def detect_anomalies(df, contamination=0.05):
    """
    Detect anomalous price behavior using DBSCAN
    """
    features = engineer_features(df)
    
    # Select features for anomaly detection
    anomaly_features = features[[
        'body_pct', 'range', 'price_momentum', 'volatility_5s', 'volatility_30s'
    ]].copy()
    
    # Standardize
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(anomaly_features)
    
    # Apply DBSCAN
    dbscan = DBSCAN(eps=0.5, min_samples=10)
    labels = dbscan.fit_predict(scaled_features)
    
    # Label outliers (-1 from DBSCAN)
    df['is_anomaly'] = (labels == -1).astype(int)
    anomalies = df[df['is_anomaly'] == 1].copy()
    
    return anomalies


def identify_trend_phases(df):
    """
    Identify distinct trend phases in the data
    """
    df = df.copy()
    
    # Calculate moving averages
    df['sma_fast'] = df['Close'].rolling(10).mean()
    df['sma_slow'] = df['Close'].rolling(30).mean()
    
    # Determine trend
    df['trend'] = 'neutral'
    df.loc[df['sma_fast'] > df['sma_slow'], 'trend'] = 'uptrend'
    df.loc[df['sma_fast'] < df['sma_slow'], 'trend'] = 'downtrend'
    
    # Identify trend changes
    df['trend_change'] = df['trend'] != df['trend'].shift(1)
    
    # Calculate phase statistics
    phases = []
    current_trend = None
    phase_start = 0
    
    for idx, row in df.iterrows():
        if row['trend_change'] or idx == df.index[-1]:
            if current_trend is not None:
                phase_data = df.loc[phase_start:idx]
                phases.append({
                    'start_time': df.loc[phase_start, 'Local'],
                    'end_time': row['Local'],
                    'trend': current_trend,
                    'duration_seconds': len(phase_data),
                    'price_change': df.loc[idx, 'Close'] - df.loc[phase_start, 'Close'],
                    'max_high': phase_data['High'].max(),
                    'min_low': phase_data['Low'].min(),
                })
            current_trend = row['trend']
            phase_start = idx
    
    return pd.DataFrame(phases)


def calculate_pattern_metrics(df):
    """
    Calculate comprehensive pattern metrics
    """
    metrics = {}
    
    # Price metrics
    metrics['total_range'] = df['High'].max() - df['Low'].min()
    metrics['avg_body_size'] = abs(df['Close'] - df['Open']).mean()
    metrics['avg_candle_range'] = (df['High'] - df['Low']).mean()
    
    # Volatility metrics
    metrics['price_volatility'] = df['Close'].std()
    metrics['returns_volatility'] = df['Close'].pct_change().std()
    
    # Directional metrics
    bullish_candles = (df['Close'] > df['Open']).sum()
    bearish_candles = (df['Close'] < df['Open']).sum()
    metrics['bullish_ratio'] = bullish_candles / len(df)
    metrics['bearish_ratio'] = bearish_candles / len(df)
    
    # Momentum metrics
    metrics['total_momentum'] = df['Close'].iloc[-1] - df['Close'].iloc[0]
    metrics['max_drawdown'] = (df['Close'].cummax() - df['Close']).max()
    metrics['max_runup'] = (df['Close'] - df['Close'].cummin()).max()
    
    return metrics


def analyze_patterns(df):
    """
    Main function to perform ML-based pattern analysis
    """
    print("\n=== ML Pattern Recognition ===")
    
    # 1. Cluster analysis
    df_clustered, cluster_summary = cluster_price_behavior(df)
    print(f"\n1. Identified {len(cluster_summary)} distinct price behavior clusters:")
    for _, cluster in cluster_summary.iterrows():
        print(f"   Cluster {int(cluster['cluster'])}: {cluster['count']} candles, "
              f"Avg Body: {cluster['avg_body']:.2f}, "
              f"Bullish: {cluster['bullish_pct']:.1f}%")
    
    # 2. Detect breakouts
    breakouts = identify_breakout_patterns(df)
    if len(breakouts) > 0:
        print(f"\n2. Detected {len(breakouts)} significant breakout events:")
        bullish_breakouts = (breakouts['direction'] == 'bullish').sum()
        bearish_breakouts = (breakouts['direction'] == 'bearish').sum()
        print(f"   Bullish breakouts: {bullish_breakouts}")
        print(f"   Bearish breakouts: {bearish_breakouts}")
    else:
        print("\n2. No significant breakout events detected")
    
    # 3. Detect anomalies
    anomalies = detect_anomalies(df)
    if len(anomalies) > 0:
        print(f"\n3. Detected {len(anomalies)} anomalous price behaviors:")
        print(f"   Average anomaly magnitude: {abs(anomalies['Close'] - anomalies['Open']).mean():.2f} points")
    else:
        print("\n3. No significant anomalies detected")
    
    # 4. Identify trend phases
    phases = identify_trend_phases(df)
    if len(phases) > 0:
        print(f"\n4. Identified {len(phases)} distinct trend phases:")
        for _, phase in phases.iterrows():
            print(f"   {phase['trend'].capitalize()}: {phase['duration_seconds']}s, "
                  f"Change: {phase['price_change']:+.2f} points")
    
    # 5. Swing points
    highs, lows = detect_swing_points(df)
    print(f"\n5. Detected swing points:")
    print(f"   Swing highs: {len(highs)}")
    print(f"   Swing lows: {len(lows)}")
    
    # 6. Overall metrics
    metrics = calculate_pattern_metrics(df)
    print(f"\n6. Pattern Metrics:")
    print(f"   Total Range: {metrics['total_range']:.2f} points")
    print(f"   Price Volatility: {metrics['price_volatility']:.2f}")
    print(f"   Bullish/Bearish Ratio: {metrics['bullish_ratio']:.2%} / {metrics['bearish_ratio']:.2%}")
    print(f"   Max Drawdown: {metrics['max_drawdown']:.2f} points")
    print(f"   Max Runup: {metrics['max_runup']:.2f} points")
    
    return {
        'df_clustered': df_clustered,
        'cluster_summary': cluster_summary,
        'breakouts': breakouts,
        'anomalies': anomalies,
        'phases': phases,
        'metrics': metrics,
        'swing_highs': highs,
        'swing_lows': lows,
    }
