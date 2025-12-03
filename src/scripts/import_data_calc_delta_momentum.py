import argparse
import os
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def main(input_path: Path, out_dir: Path, window: int = 5, top_n: int = 5):
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    # try to parse Local column robustly
    df["Local"] = pd.to_datetime(df["Local"].astype(str).str.replace(" UTC+02:00", ""), format="%d.%m.%Y %H:%M:%S.%f", errors="coerce")
    df["Mid"] = (df["Ask"] + df["Bid"]) / 2

    # timing
    df["TickTimeDiff_ms"] = df["Local"].diff().dt.total_seconds() * 1000

    # compute mid delta and zscore
    df["MidDelta"] = df["Mid"].diff()
    df["ZScore"] = df["MidDelta"].rolling(window=window).apply(
        lambda x: (x.iloc[-1] - x.mean()) / x.std() if len(x) == window and x.std() != 0 else np.nan,
        raw=False,
    )

    # simple burst detection (copied logic)
    def detect_bursts(df, z_col="ZScore", threshold=1.9, min_ticks=1):
        is_burst = df[z_col].abs() > threshold
        bursts = []
        burst_active = False
        start = None
        for i, val in enumerate(is_burst):
            if val and not burst_active:
                burst_active = True
                start = i
            elif not val and burst_active:
                end = i - 1
                if end - start + 1 >= min_ticks:
                    bursts.append(_burst_metrics(df, start, end))
                burst_active = False
                start = None
        if burst_active and start is not None:
            end = len(df) - 1
            if end - start + 1 >= min_ticks:
                bursts.append(_burst_metrics(df, start, end))
        return pd.DataFrame(bursts)


    def _burst_metrics(df, start_idx, end_idx):
        start_time = df["Local"].iat[start_idx]
        end_time = df["Local"].iat[end_idx]
        duration_s = (end_time - start_time).total_seconds()
        duration_ms = duration_s * 1000.0
        ticks = end_idx - start_idx + 1
        price_start = df["Mid"].iat[start_idx]
        price_end = df["Mid"].iat[end_idx]
        price_change = price_end - price_start
        abs_price_change = abs(price_change)
        if start_idx > 0:
            prev_idx = start_idx - 1
        else:
            prev_idx = start_idx
        prev_time = df["Local"].iat[prev_idx]
        prev_price = df["Mid"].iat[prev_idx]
        price_change_prev = price_end - prev_price
        abs_price_change_prev = abs(price_change_prev)
        duration_prev_s = (end_time - prev_time).total_seconds()
        duration_prev_ms = duration_prev_s * 1000.0
        z_series = df["ZScore"].iloc[start_idx:end_idx + 1].abs().dropna()
        mean_z = float(z_series.mean()) if not z_series.empty else 0.0
        max_z = float(z_series.max()) if not z_series.empty else 0.0
        mean_tick_ms = float(df["TickTimeDiff_ms"].iloc[start_idx + 1:end_idx + 1].mean()) if end_idx > start_idx else np.nan
        speed_price_per_sec = abs_price_change / duration_s if duration_s > 0 else np.inf
        speed_price_per_tick = abs_price_change / ticks if ticks > 0 else np.inf
        max_z_per_sec = max_z / duration_s if duration_s > 0 else np.inf
        speed_prev_price_per_sec = abs_price_change_prev / duration_prev_s if duration_prev_s > 0 else np.inf
        speed_prev_price_per_tick = abs_price_change_prev / max(1, ticks) if ticks > 0 else np.inf
        return {
            "start_idx": start_idx,
            "end_idx": end_idx,
            "start_time": start_time,
            "end_time": end_time,
            "duration_s": duration_s,
            "duration_ms": duration_ms,
            "ticks": ticks,
            "price_change": price_change,
            "abs_price_change": abs_price_change,
            "mean_z": mean_z,
            "max_z": max_z,
            "mean_tick_ms": mean_tick_ms,
            "speed_price_per_sec": speed_price_per_sec,
            "speed_price_per_tick": speed_price_per_tick,
            "max_z_per_sec": max_z_per_sec,
            "price_change_prev": price_change_prev,
            "abs_price_change_prev": abs_price_change_prev,
            "duration_prev_s": duration_prev_s,
            "duration_prev_ms": duration_prev_ms,
            "speed_prev_price_per_sec": speed_prev_price_per_sec,
            "speed_prev_price_per_tick": speed_prev_price_per_tick,
        }

    # auto threshold
    def auto_detect_threshold(df, z_col="ZScore", min_events=3, p_list=None, min_threshold=0.5):
        z_abs = df[z_col].abs().dropna()
        if z_abs.empty:
            return 1.9, ("none", None)
        p_list = p_list or [0.999, 0.995, 0.99, 0.98, 0.95, 0.90, 0.85]
        for p in p_list:
            q = float(z_abs.quantile(p))
            if q < min_threshold:
                continue
            count = int((z_abs > q).sum())
            if count >= min_events:
                return q, ("percentile", p)
        mu = float(z_abs.mean())
        sigma = float(z_abs.std())
        q_sigma = mu + 3 * sigma
        if q_sigma >= min_threshold and (z_abs > q_sigma).sum() >= 1:
            return float(q_sigma), ("mu+3sigma", None)
        max_z = float(z_abs.max()) if not z_abs.empty else 1.9
        if max_z >= min_threshold:
            return max_z, ("max", None)
        return 1.9, ("default", None)

    z_threshold, threshold_info = auto_detect_threshold(df, z_col="ZScore")
    bursts_df = detect_bursts(df, z_col="ZScore", threshold=z_threshold, min_ticks=1)

    # Extract top bursts by duration and speed
    top_bursts = pd.DataFrame()
    if not bursts_df.empty:
        top_by_duration = bursts_df.nlargest(top_n, "duration_ms")
        top_by_speed = bursts_df.nlargest(top_n, "speed_price_per_sec")
        top_bursts = pd.concat([top_by_duration, top_by_speed]).drop_duplicates(subset=["start_idx", "end_idx"])

    # Create detailed z-score report for top bursts
    z_scores_report = []
    for _, row in top_bursts.iterrows():
        start_idx = int(row["start_idx"])
        end_idx = int(row["end_idx"])
        burst_z_scores = df["ZScore"].iloc[start_idx:end_idx + 1].abs().dropna()
        for tick_offset, z in enumerate(burst_z_scores):
            tick_idx = start_idx + tick_offset
            z_scores_report.append({
                "burst_start_time": row["start_time"],
                "tick_index": tick_idx,
                "tick_time": df["Local"].iat[tick_idx],
                "z_score": z,
                "mid_delta": df["MidDelta"].iat[tick_idx],
                "mid_price": df["Mid"].iat[tick_idx],
                "burst_duration_ms": row.get("duration_ms", 0.0),
                "burst_duration_prev_ms": row.get("duration_prev_ms", 0.0),
            })

    # Save detailed reports
    if not bursts_df.empty:
        bursts_df.to_csv(out_dir / "bursts_summary.csv", index=False)
    if z_scores_report:
        pd.DataFrame(z_scores_report).to_csv(out_dir / "burst_zscore_details.csv", index=False)
        print(f"  Saved detailed Z-score report: burst_zscore_details.csv with {len(z_scores_report)} Z-score entries")

    # Plot main figure and save
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df["Local"], df["Mid"], color="gray", label="Mid Price", linewidth=1)
    
    # Highlight top bursts on main plot
    if not top_bursts.empty:
        top_longest = top_bursts.nlargest(3, "duration_ms")
        top_fastest = top_bursts.nlargest(3, "speed_price_per_sec")
        
        for _, row in top_longest.iterrows():
            start_time = row["start_time"]
            end_time = row["end_time"]
            ax.axvline(start_time, color="lime", alpha=0.6, linestyle="--", linewidth=1.5)
            mid_price = row.get("abs_price_change_prev", 0.0)
            dur_ms = int(row.get("duration_prev_ms", row.get("duration_ms", 0.0)))
            ax.text(start_time, df["Mid"].max() * 0.95, f"L:{dur_ms}ms", rotation=90, fontsize=8, color="lime")
        
        for _, row in top_fastest.iterrows():
            start_time = row["start_time"]
            ax.axvline(start_time, color="red", alpha=0.6, linestyle="--", linewidth=1.5)
            speed = row.get("speed_prev_price_per_sec", 0.0)
            ax.text(start_time, df["Mid"].min() * 1.05, f"F:{speed:.2f}/s", rotation=90, fontsize=8, color="red")
    
    ax.set_title(f"CFD Tick Chart: Z-Score Bursts (|Z| > {z_threshold:.3f}) — Top {top_n}")
    ax.set_xlabel("Time")
    ax.set_ylabel("Mid Price")
    ax.grid(True, alpha=0.3)
    ax.legend()

    main_fname = f"bursts_main_{input_path.stem}_thr_{z_threshold:.3f}_top{top_n}.png"
    fig.savefig(out_dir / main_fname, dpi=150)

    # Save zoom images for bursts
    def save_zoomed_burst_plot(df, row, idx):
        dur_ms = float(row.get("duration_ms", row.get("duration_s", 0.0) * 1000.0))
        pad_ms = max(1000.0, dur_ms * 2.0)
        start = row["start_time"] - pd.Timedelta(milliseconds=pad_ms)
        end = row["end_time"] + pd.Timedelta(milliseconds=pad_ms)
        subset = df[(df["Local"] >= start) & (df["Local"] <= end)]
        if subset.empty:
            return None
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(subset["Local"], subset["Mid"], color="gray")
        ax.axvspan(row["start_time"], row["end_time"], color="orange", alpha=0.35)
        center_time = row["start_time"] + (row["end_time"] - row["start_time"]) / 2
        mid_price_at_center = subset.loc[(subset["Local"] - center_time).abs().idxmin(), "Mid"]
        abs_change = row.get('abs_price_change_prev', row.get('abs_price_change', 0.0))
        dur_prev_ms = int(row.get('duration_prev_ms', int(row.get('duration_ms', row.get('duration_s', 0.0) * 1000.0))))
        speed = row.get('speed_prev_price_per_sec', row.get('speed_price_per_sec', 0.0))
        ann = f"Δ{abs_change:.4f}  {dur_prev_ms}ms  {speed:.4f}/s"
        ax.annotate(ann, xy=(center_time, mid_price_at_center), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color="black")
        ax.set_title(f"Burst zoom: {row['start_time']}  dur={dur_prev_ms}ms")
        ax.set_xlabel("Time")
        ax.set_ylabel("Mid Price")
        ax.grid(True)
        plt.tight_layout()
        # filename
        st = row['start_time']
        ms = int(st.microsecond / 1000)
        start_str = st.strftime('%Y%m%d_%H%M%S') + f"_{ms:03d}"
        dur_ms_i = int(row.get('duration_ms', int(row.get('duration_s', 0.0) * 1000.0)))
        prev_ms_i = int(row.get('duration_prev_ms', int(row.get('duration_prev_s', 0.0) * 1000.0)))
        if dur_ms_i == 0 and prev_ms_i > 0:
            dur_part = f"{prev_ms_i}ms_prev"
        elif dur_ms_i != 0 and prev_ms_i != 0 and prev_ms_i != dur_ms_i:
            dur_part = f"{dur_ms_i}ms_prev{prev_ms_i}ms"
        else:
            dur_part = f"{dur_ms_i}ms"
        filename = f"burst_{idx}_{start_str}_dur_{dur_part}.png"
        out_path = out_dir / filename
        try:
            fig.savefig(out_path, dpi=150)
        except Exception:
            out_path = None
        plt.close(fig)
        return out_path

    saved_files = []
    if not bursts_df.empty:
        for i, row in bursts_df.reset_index(drop=True).iterrows():
            saved = save_zoomed_burst_plot(df, row, i)
            if saved:
                saved_files.append(saved)

    print(f"Saved main: {main_fname}, zoomed: {len(saved_files)} files into {out_dir}")
    
    # Print summary of top bursts with their Z-scores
    print(f"\n=== Top {min(top_n, len(top_bursts))} Bursts (by duration & speed) ===")
    for idx, (_, row) in enumerate(top_bursts.iterrows(), 1):
        start_idx = int(row["start_idx"])
        end_idx = int(row["end_idx"])
        burst_z_scores = df["ZScore"].iloc[start_idx:end_idx + 1].abs().dropna()
        print(f"\nBurst {idx}: {row['start_time']} | dur={row.get('duration_ms', 0.0):.0f}ms | "
              f"Δ{row.get('abs_price_change_prev', 0.0):.4f} | speed={row.get('speed_prev_price_per_sec', 0.0):.4f}/s")
        print(f"  Z-scores in burst ({len(burst_z_scores)} ticks): {burst_z_scores.values}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Detect z-score bursts and save charts")
    p.add_argument("--input", "-i", type=Path, required=True, help="input CSV file path")
    p.add_argument("--out", "-o", type=Path, default=Path("momentum_moves_charts"), help="output directory for charts")
    p.add_argument("--window", type=int, default=5)
    p.add_argument("--top", type=int, default=5)
    args = p.parse_args()
    main(args.input, args.out, window=args.window, top_n=args.top)
