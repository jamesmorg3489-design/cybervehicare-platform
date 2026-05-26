"""
=============================================================
Cybervehicare - Vehicle Health Monitoring Framework
Phase 2: Dataset Pipeline
=============================================================
File path  : cybervehicare/data_pipeline/data_pipeline.py
Run command: python data_pipeline/data_pipeline.py
=============================================================
"""

import os
import json
import hashlib
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils import resample

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
RAW_CSV      = Path("data/raw/vehicle_telemetry.csv")
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR   = Path("data/reports")
TARGET_COL    = "maintenance_status"
LABEL_ORDER   = ["NORMAL", "WARNING", "CRITICAL"]
RANDOM_STATE  = 42

NUMERIC_FEATURES = [
    "odometer_reading", "engine_temp_c", "engine_rpm", "oil_pressure_psi",
    "coolant_temp_c", "fuel_level_percent", "fuel_consumption_lph",
    "vibration_level", "engine_hours", "brake_fluid_level_psi",
    "brake_pad_wear_mm", "brake_temp_c", "abs_fault_indicator",
    "battery_voltage_v", "battery_current_a", "battery_temp_c",
    "battery_charge_percent", "battery_health_percent",
    "vehicle_speed_kph", "tyre_pressure_psi", "fault_indicator",
    "engine_failure_imminent", "brake_issue_imminent", "battery_issue_imminent",
]

CATEGORICAL_FEATURES = ["organisation_type", "vehicle_type", "failure_type"]
DROP_COLS            = ["vehicle_id", "timestamp", "gps_latitude", "gps_longitude"]


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────
# STEP 1 — LOAD & VALIDATE
# ─────────────────────────────────────────────
def load_and_validate(path: Path) -> pd.DataFrame:
    banner("STEP 1 · Load & Validate Raw Data")

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at '{path}'.\n"
            "Place vehicle_telemetry.csv inside  data/raw/  before running."
        )

    df = pd.read_csv(path)
    print(f"  Rows         : {len(df):,}")
    print(f"  Columns      : {df.shape[1]}")
    print(f"  Memory usage : {df.memory_usage(deep=True).sum() / 1024:.1f} KB")

    # ── Schema check ──
    required = NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COL] + DROP_COLS
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing expected columns: {missing_cols}")
    print("  Schema check : PASSED ✓")

    # ── Target label check ──
    actual_labels = set(df[TARGET_COL].unique())
    expected_labels = set(LABEL_ORDER)
    if not expected_labels.issubset(actual_labels):
        raise ValueError(f"Unexpected labels in target: {actual_labels}")
    print(f"  Target labels: {sorted(actual_labels)}")

    # ── Class distribution ──
    print("\n  Class distribution (raw):")
    vc = df[TARGET_COL].value_counts()
    for label in LABEL_ORDER:
        count = vc.get(label, 0)
        pct   = 100 * count / len(df)
        bar   = "█" * int(pct / 2)
        print(f"    {label:<10}: {count:>5} ({pct:5.1f}%)  {bar}")

    # ── Null check ──
    nulls = df.isnull().sum()
    null_cols = nulls[nulls > 0]
    if len(null_cols) == 0:
        print("  Null values  : NONE ✓")
    else:
        print(f"  Null values  : found in {len(null_cols)} columns (will be imputed)")

    # ── Duplicate check ──
    dupes = df.duplicated().sum()
    print(f"  Duplicates   : {dupes}")

    return df


# ─────────────────────────────────────────────
# STEP 2 — CLEAN
# ─────────────────────────────────────────────
def clean(df: pd.DataFrame) -> pd.DataFrame:
    banner("STEP 2 · Clean Data")

    original_len = len(df)

    # Drop full duplicates
    df = df.drop_duplicates()
    print(f"  Duplicates removed : {original_len - len(df)}")

    # Impute numeric nulls with median (per vehicle_type group for realism)
    for col in NUMERIC_FEATURES:
        if df[col].isnull().any():
            medians = df.groupby("vehicle_type")[col].transform("median")
            df[col] = df[col].fillna(medians).fillna(df[col].median())
            print(f"  Imputed (median)   : {col}")

    # Impute categorical nulls with mode
    for col in CATEGORICAL_FEATURES:
        if df[col].isnull().any():
            mode_val = df[col].mode()[0]
            df[col] = df[col].fillna(mode_val)
            print(f"  Imputed (mode)     : {col}  → '{mode_val}'")

    # ── Domain-specific cleaning (before outlier clipping) ──
    # Fuel level must be within physical bounds [0, 100]
    df["fuel_level_percent"] = df["fuel_level_percent"].clip(lower=0, upper=100)

    # Vibration and brake temperature have physical minimums
    df["vibration_level"] = df["vibration_level"].clip(lower=0)
    df["brake_temp_c"]    = df["brake_temp_c"].clip(lower=20)

    # Boolean/flag columns must be exact 0 or 1 integers
    binary_cols = [
        "abs_fault_indicator", "engine_failure_imminent",
        "brake_issue_imminent", "battery_issue_imminent", "fault_indicator",
    ]
    for col in binary_cols:
        df[col] = df[col].round().clip(lower=0, upper=1).astype(int)

    # Sort by vehicle_id and timestamp for chronological integrity
    df = df.sort_values(["vehicle_id", "timestamp"]).reset_index(drop=True)
    print(f"  Domain clipping    : fuel_level_percent [0,100], "
          f"vibration_level [0,∞), brake_temp_c [20,∞)")
    print(f"  Binary cols forced : {binary_cols}")
    print(f"  Sorted by          : vehicle_id, timestamp")

    # Clip obvious sensor outliers (3-sigma rule per column)
    clipped_total = 0
    for col in NUMERIC_FEATURES:
        mu, sigma = df[col].mean(), df[col].std()
        lo, hi    = mu - 3 * sigma, mu + 3 * sigma
        before    = ((df[col] < lo) | (df[col] > hi)).sum()
        df[col]   = df[col].clip(lower=lo, upper=hi)
        clipped_total += before
    print(f"  Outliers clipped   : {clipped_total} data points (3σ rule)")

    # Re-force binary columns to exact 0/1 integers after 3σ clipping
    for col in binary_cols:
        df[col] = df[col].round().clip(lower=0, upper=1).astype(int)
    print(f"  Binary cols re-forced (post 3σ) : {binary_cols}")

    # Normalise timestamp before sort
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Re-sort by vehicle_id and timestamp after all cleaning is complete
    df = df.sort_values(["vehicle_id", "timestamp"]).reset_index(drop=True)
    print(f"  Re-sorted by       : vehicle_id, timestamp")
    print(f"  Remaining rows     : {len(df):,}")

    return df


# ─────────────────────────────────────────────
# STEP 3 — FEATURE ENGINEERING
# ─────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    banner("STEP 3 · Feature Engineering")

    # Derived features
    df["engine_temp_rpm_ratio"]    = df["engine_temp_c"] / (df["engine_rpm"] + 1)
    df["battery_stress_index"]     = (df["battery_current_a"].abs() /
                                      (df["battery_voltage_v"] + 0.001)) * \
                                      (1 - df["battery_health_percent"] / 100)
    df["brake_wear_heat_ratio"]    = df["brake_pad_wear_mm"] * df["brake_temp_c"] / 100
    df["fuel_efficiency_score"]    = df["vehicle_speed_kph"] / (df["fuel_consumption_lph"] + 0.001)
    df["combined_failure_risk"]    = (df["engine_failure_imminent"] +
                                      df["brake_issue_imminent"]    +
                                      df["battery_issue_imminent"])

    new_cols = [
        "engine_temp_rpm_ratio", "battery_stress_index",
        "brake_wear_heat_ratio", "fuel_efficiency_score",
        "combined_failure_risk",
    ]
    print(f"  New features added : {new_cols}")

    # Encode target with ordered mapping
    label_map = {lbl: i for i, lbl in enumerate(LABEL_ORDER)}
    df["label"] = df[TARGET_COL].map(label_map)
    print(f"  Label encoding     : {label_map}")

    return df


# ─────────────────────────────────────────────
# STEP 4 — ENCODE CATEGORICALS
# ─────────────────────────────────────────────
def encode_categoricals(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    banner("STEP 4 · Encode Categorical Features")

    encoders = {}
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col]    = {str(cls): int(idx) for idx, cls in enumerate(le.classes_)}
        print(f"  {col:<20}: {encoders[col]}")

    return df, encoders


# ─────────────────────────────────────────────
# STEP 5 — SPLIT
# ─────────────────────────────────────────────
def split_dataset(df: pd.DataFrame) -> tuple:
    banner("STEP 5 · Train / Validation / Test Split  (70 / 15 / 15)")

    all_feature_cols = (
        NUMERIC_FEATURES
        + [f"{c}_enc" for c in CATEGORICAL_FEATURES]
        + ["engine_temp_rpm_ratio", "battery_stress_index",
           "brake_wear_heat_ratio", "fuel_efficiency_score",
           "combined_failure_risk"]
    )

    X = df[all_feature_cols]
    y = df["label"]

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=RANDOM_STATE
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=RANDOM_STATE
    )

    for name, xs in [("Train", X_train), ("Val", X_val), ("Test", X_test)]:
        print(f"  {name:<6}: {len(xs):>5} rows")

    return X_train, X_val, X_test, y_train, y_val, y_test, all_feature_cols


# ─────────────────────────────────────────────
# STEP 6 — SCALE
# ─────────────────────────────────────────────
def scale_features(X_train, X_val, X_test):
    banner("STEP 6 · StandardScaler Normalisation")

    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train),
                              columns=X_train.columns, index=X_train.index)
    X_val_s   = pd.DataFrame(scaler.transform(X_val),
                              columns=X_val.columns,   index=X_val.index)
    X_test_s  = pd.DataFrame(scaler.transform(X_test),
                              columns=X_test.columns,  index=X_test.index)

    print(f"  Scaler fitted on {len(X_train)} train rows.")
    print(f"  Mean (first 3 cols): {scaler.mean_[:3].round(3)}")
    print(f"  Std  (first 3 cols): {scaler.scale_[:3].round(3)}")

    return X_train_s, X_val_s, X_test_s, scaler


# ─────────────────────────────────────────────
# STEP 7 — BALANCE (oversample minority)
# ─────────────────────────────────────────────
def balance_train(X_train_s, y_train):
    banner("STEP 7 · Balance Training Set (Oversample Minority Classes)")

    train = pd.concat([X_train_s, y_train], axis=1)
    counts = train["label"].value_counts()
    print("  Before balancing:")
    for lbl, cnt in counts.items():
        print(f"    label={lbl}  {LABEL_ORDER[lbl]:<10}: {cnt}")

    majority_n = counts.max()
    parts = []
    for lbl in sorted(counts.index):
        subset = train[train["label"] == lbl]
        if len(subset) < majority_n:
            subset = resample(subset, replace=True, n_samples=majority_n,
                              random_state=RANDOM_STATE)
        parts.append(subset)

    balanced = pd.concat(parts).sample(frac=1, random_state=RANDOM_STATE)
    print("\n  After balancing:")
    for lbl, cnt in balanced["label"].value_counts().sort_index().items():
        print(f"    label={lbl}  {LABEL_ORDER[lbl]:<10}: {cnt}")

    X_bal = balanced.drop(columns="label")
    y_bal = balanced["label"]
    return X_bal, y_bal


# ─────────────────────────────────────────────
# STEP 8 — SAVE ARTIFACTS
# ─────────────────────────────────────────────
def save_artifacts(
    df, X_train, X_val, X_test, y_train, y_val, y_test,
    X_bal, y_bal, scaler, encoders, feature_cols
):
    banner("STEP 8 · Save Processed Artifacts")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── CSVs ──
    files = {
        "train.csv"         : pd.concat([X_train, y_train], axis=1),
        "val.csv"           : pd.concat([X_val,   y_val  ], axis=1),
        "test.csv"          : pd.concat([X_test,  y_test ], axis=1),
        "train_balanced.csv": pd.concat([X_bal,   y_bal  ], axis=1),
    }
    for fname, frame in files.items():
        out = PROCESSED_DIR / fname
        frame.to_csv(out, index=False)
        print(f"  Saved {out}  ({len(frame):,} rows)")

    # Full cleaned dataset (with original columns, before drop)
    clean_out = PROCESSED_DIR / "cleaned_full.csv"
    df.to_csv(clean_out, index=False)
    print(f"  Saved {clean_out}  ({len(df):,} rows)")

    # Additional cleaned copy — vehicle_telemetry_cleaned.csv
    telemetry_cleaned_out = PROCESSED_DIR / "vehicle_telemetry_cleaned.csv"
    df.to_csv(telemetry_cleaned_out, index=False)
    print(f"  Saved {telemetry_cleaned_out}  ({len(df):,} rows)")

    # ── Dataset summary CSV ──
    summary_rows = []
    for col in df.columns:
        col_data = df[col]
        summary_rows.append({
            "column"      : col,
            "dtype"       : str(col_data.dtype),
            "non_null"    : int(col_data.notna().sum()),
            "null_count"  : int(col_data.isna().sum()),
            "unique_count": int(col_data.nunique()),
            "mean"        : round(col_data.mean(), 4) if pd.api.types.is_numeric_dtype(col_data) else None,
            "std"         : round(col_data.std(),  4) if pd.api.types.is_numeric_dtype(col_data) else None,
            "min"         : round(col_data.min(),  4) if pd.api.types.is_numeric_dtype(col_data) else None,
            "max"         : round(col_data.max(),  4) if pd.api.types.is_numeric_dtype(col_data) else None,
        })
    summary_df   = pd.DataFrame(summary_rows)
    summary_path = REPORTS_DIR / "dataset_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"  Saved {summary_path}")

    # ── Class distribution graph ──
    class_counts = df[TARGET_COL].value_counts().reindex(LABEL_ORDER)
    colors = ["#4CAF50", "#FF9800", "#F44336"]          # green / amber / red
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(LABEL_ORDER, class_counts.values, color=colors, edgecolor="white",
                  linewidth=0.8, width=0.55)
    for bar, val in zip(bars, class_counts.values):
        pct = 100 * val / len(df)
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + len(df) * 0.005,
                f"{val:,}\n({pct:.1f}%)",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_title("Class Distribution — maintenance_status", fontsize=13, fontweight="bold", pad=14)
    ax.set_xlabel("Maintenance Status", fontsize=11)
    ax.set_ylabel("Record Count",       fontsize=11)
    ax.set_ylim(0, class_counts.max() * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    dist_path = REPORTS_DIR / "class_distribution.png"
    plt.savefig(dist_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {dist_path}")

    # ── Scaler params (JSON, no joblib dependency) ──
    scaler_meta = {
        "mean"  : scaler.mean_.tolist(),
        "scale" : scaler.scale_.tolist(),
        "feature_names": feature_cols,
    }
    scaler_path = PROCESSED_DIR / "scaler_params.json"
    with open(scaler_path, "w") as f:
        json.dump(scaler_meta, f, indent=2)
    print(f"  Saved {scaler_path}")

    # ── Label / encoder metadata ──
    meta = {
        "label_map"         : {lbl: i for i, lbl in enumerate(LABEL_ORDER)},
        "label_order"       : LABEL_ORDER,
        "categorical_encoders": encoders,
        "feature_columns"   : feature_cols,
        "target_column"     : TARGET_COL,
        "generated_at"      : datetime.utcnow().isoformat() + "Z",
    }
    meta_path = PROCESSED_DIR / "pipeline_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved {meta_path}")

    # ── Data quality report ──
    report = {
        "dataset"           : str(RAW_CSV),
        "total_rows"        : len(df),
        "total_columns"     : df.shape[1],
        "null_values"       : int(df.isnull().sum().sum()),
        "class_distribution": df[TARGET_COL].value_counts().to_dict(),
        "train_rows"        : len(X_train),
        "val_rows"          : len(X_val),
        "test_rows"         : len(X_test),
        "balanced_train_rows": len(X_bal),
        "numeric_features"  : NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "engineered_features": [
            "engine_temp_rpm_ratio", "battery_stress_index",
            "brake_wear_heat_ratio", "fuel_efficiency_score", "combined_failure_risk",
        ],
        "pipeline_steps"    : [
            "load_and_validate", "clean", "engineer_features",
            "encode_categoricals", "split", "scale", "balance"
        ],
        "generated_at"      : datetime.utcnow().isoformat() + "Z",
    }
    report_path = REPORTS_DIR / "data_quality_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Saved {report_path}")

    return files


# ─────────────────────────────────────────────
# STEP 9 — INTEGRITY CHECK
# ─────────────────────────────────────────────
def integrity_check():
    banner("STEP 9 · Integrity Verification")

    expected = [
        PROCESSED_DIR / "train.csv",
        PROCESSED_DIR / "val.csv",
        PROCESSED_DIR / "test.csv",
        PROCESSED_DIR / "train_balanced.csv",
        PROCESSED_DIR / "cleaned_full.csv",
        PROCESSED_DIR / "scaler_params.json",
        PROCESSED_DIR / "pipeline_metadata.json",
        REPORTS_DIR   / "data_quality_report.json",
        PROCESSED_DIR / "vehicle_telemetry_cleaned.csv",
        REPORTS_DIR   / "dataset_summary.csv",
        REPORTS_DIR   / "class_distribution.png",
    ]

    all_ok = True
    for p in expected:
        exists = p.exists()
        size   = p.stat().st_size if exists else 0
        status = "✓" if exists else "✗ MISSING"
        print(f"  {status}  {p}  ({size:,} bytes)")
        if not exists:
            all_ok = False

    if all_ok:
        print("\n  All pipeline artifacts verified. Phase 2 COMPLETE ✓")
    else:
        print("\n  WARNING: some files are missing!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "═" * 60)
    print("  CYBERVEHICARE · PHASE 2 — DATASET PIPELINE")
    print("  " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    print("═" * 60)

    df                              = load_and_validate(RAW_CSV)
    df                              = clean(df)
    df                              = engineer_features(df)
    df, encoders                    = encode_categoricals(df)
    X_tr, X_v, X_te, y_tr, y_v, y_te, feat_cols = split_dataset(df)
    X_tr_s, X_v_s, X_te_s, scaler  = scale_features(X_tr, X_v, X_te)
    X_bal, y_bal                    = balance_train(X_tr_s, y_tr)
    save_artifacts(df, X_tr_s, X_v_s, X_te_s, y_tr, y_v, y_te,
                   X_bal, y_bal, scaler, encoders, feat_cols)
    integrity_check()

    print("\n  Next step → Phase 3: python model_training/train_model.py\n")


if __name__ == "__main__":
    main()
