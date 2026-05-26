"""
=============================================================
Cybervehicare - Vehicle Health Monitoring Framework
Phase 3: Predictive Maintenance Model Training
=============================================================
File path  : cybervehicare/ml/train_model.py
Run command: python ml/train_model.py
=============================================================
"""

import json
import warnings
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, classification_report, confusion_matrix,
    ConfusionMatrixDisplay,
)

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR   = Path("data/reports")
MODELS_DIR    = Path("ml/models")
TARGET_COL    = "label"
LABEL_NAMES   = ["NORMAL", "WARNING", "CRITICAL"]   # 0, 1, 2
RANDOM_STATE  = 42

TRAIN_CSV     = PROCESSED_DIR / "train_balanced.csv"
VAL_CSV       = PROCESSED_DIR / "val.csv"
TEST_CSV      = PROCESSED_DIR / "test.csv"
METADATA_JSON = PROCESSED_DIR / "pipeline_metadata.json"


def banner(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────
# STEP 1 — SAFETY CHECKS & LOAD
# ─────────────────────────────────────────────
def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    banner("STEP 1 · Safety Checks & Load Datasets")

    # ── File existence checks ──
    for path in [TRAIN_CSV, VAL_CSV, TEST_CSV, METADATA_JSON]:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: '{path}'\n"
                "Run Phase 2 (data_pipeline/data_pipeline.py) first."
            )
    print("  File existence   : ALL PRESENT ✓")

    # ── Model output folder check / create ──
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Output dirs      : {MODELS_DIR}  &  {REPORTS_DIR} ✓")

    # ── Load CSVs ──
    train = pd.read_csv(TRAIN_CSV)
    val   = pd.read_csv(VAL_CSV)
    test  = pd.read_csv(TEST_CSV)

    # ── Label column check ──
    for name, df in [("train_balanced", train), ("val", val), ("test", test)]:
        if TARGET_COL not in df.columns:
            raise ValueError(
                f"Target column '{TARGET_COL}' missing in {name}.csv. "
                "Re-run Phase 2 to regenerate processed files."
            )
    print(f"  Label column     : '{TARGET_COL}' found in all splits ✓")

    # ── Dataset shapes ──
    print("\n  Dataset shapes:")
    print(f"    train_balanced : {train.shape[0]:>6,} rows × {train.shape[1]} cols")
    print(f"    val            : {val.shape[0]:>6,} rows × {val.shape[1]} cols")
    print(f"    test           : {test.shape[0]:>6,} rows × {test.shape[1]} cols")

    # ── Class distributions ──
    print("\n  Class distribution:")
    for split_name, df in [("Train (balanced)", train), ("Val", val), ("Test", test)]:
        vc = df[TARGET_COL].value_counts().sort_index()
        dist = "  ".join(
            f"{LABEL_NAMES[lbl]}={cnt}({100*cnt/len(df):.1f}%)"
            for lbl, cnt in vc.items()
        )
        print(f"    {split_name:<18}: {dist}")

    return train, val, test


# ─────────────────────────────────────────────
# STEP 2 — PREPARE FEATURES
# ─────────────────────────────────────────────
def prepare_features(
    train: pd.DataFrame,
    val:   pd.DataFrame,
    test:  pd.DataFrame,
) -> tuple:
    banner("STEP 2 · Prepare Feature Matrices")

    feature_cols = [c for c in train.columns if c != TARGET_COL]

    X_train = train[feature_cols]
    y_train = train[TARGET_COL]
    X_val   = val[feature_cols]
    y_val   = val[TARGET_COL]
    X_test  = test[feature_cols]
    y_test  = test[TARGET_COL]

    print(f"  Feature columns  : {len(feature_cols)}")
    print(f"  Features         : {feature_cols}")

    return X_train, X_val, X_test, y_train, y_val, y_test, feature_cols


# ─────────────────────────────────────────────
# STEP 3 — TRAIN
# ─────────────────────────────────────────────
def train_model(X_train, y_train) -> RandomForestClassifier:
    banner("STEP 3 · Train RandomForestClassifier")

    clf = RandomForestClassifier(
        n_estimators=300,        # enough trees for stable feature importance
        max_depth=None,          # let trees grow fully
        min_samples_split=5,
        min_samples_leaf=2,
        max_features="sqrt",     # standard for classification
        class_weight="balanced", # guard against residual imbalance
        n_jobs=-1,               # use all available CPU cores
        random_state=RANDOM_STATE,
    )

    print(f"  Model            : RandomForestClassifier")
    print(f"  n_estimators     : {clf.n_estimators}")
    print(f"  max_features     : {clf.max_features}")
    print(f"  class_weight     : {clf.class_weight}")
    print(f"  Training on      : {len(X_train):,} samples …")

    start = datetime.utcnow()
    clf.fit(X_train, y_train)
    elapsed = (datetime.utcnow() - start).total_seconds()

    print(f"  Training time    : {elapsed:.1f}s")
    return clf


# ─────────────────────────────────────────────
# STEP 4 — EVALUATE
# ─────────────────────────────────────────────
def evaluate(
    clf, X_val, y_val, X_test, y_test
) -> tuple[dict, str, np.ndarray]:
    banner("STEP 4 · Evaluate on Validation & Test Sets")

    metrics = {}

    for split_name, X, y in [("Validation", X_val, y_val), ("Test", X_test, y_test)]:
        y_pred = clf.predict(X)
        acc  = accuracy_score(y, y_pred)
        prec = precision_score(y, y_pred, average="weighted", zero_division=0)
        rec  = recall_score(y, y_pred, average="weighted", zero_division=0)
        f1   = f1_score(y, y_pred, average="weighted", zero_division=0)

        print(f"\n  ── {split_name} ──")
        print(f"    Accuracy       : {acc:.4f}")
        print(f"    Precision (W)  : {prec:.4f}")
        print(f"    Recall    (W)  : {rec:.4f}")
        print(f"    F1-score  (W)  : {f1:.4f}")

        metrics[split_name.lower()] = {
            "accuracy" : round(acc,  4),
            "precision": round(prec, 4),
            "recall"   : round(rec,  4),
            "f1_score" : round(f1,   4),
        }

    # Full classification report and confusion matrix on test set
    y_test_pred = clf.predict(X_test)

    print("\n  ── Test — Classification Report ──")
    report_str = classification_report(
        y_test, y_test_pred,
        target_names=LABEL_NAMES,
        digits=4,
    )
    print(report_str)

    cm = confusion_matrix(y_test, y_test_pred)
    print("  ── Test — Confusion Matrix ──")
    header = "         " + "  ".join(f"{n:>10}" for n in LABEL_NAMES)
    print(header)
    for i, row in enumerate(cm):
        row_str = "  ".join(f"{v:>10}" for v in row)
        print(f"  {LABEL_NAMES[i]:<8} {row_str}")

    return metrics, report_str, cm


# ─────────────────────────────────────────────
# STEP 5 — SAVE ARTIFACTS
# ─────────────────────────────────────────────
def save_artifacts(
    clf, metrics, report_str, cm,
    feature_cols: list,
) -> None:
    banner("STEP 5 · Save Model & Report Artifacts")

    # ── Model pickle ──
    model_path = MODELS_DIR / "maintenance_model.pkl"
    joblib.dump(clf, model_path)
    print(f"  Saved {model_path}  ({model_path.stat().st_size / 1024:.0f} KB)")

    # ── Feature columns ──
    feat_path = MODELS_DIR / "feature_columns.json"
    with open(feat_path, "w") as f:
        json.dump({"feature_columns": feature_cols}, f, indent=2)
    print(f"  Saved {feat_path}")

    # ── Model metadata ──
    meta = {
        "model_class"      : type(clf).__name__,
        "n_estimators"     : clf.n_estimators,
        "max_features"     : clf.max_features,
        "class_weight"     : clf.class_weight,
        "random_state"     : clf.random_state,
        "n_features"       : len(feature_cols),
        "label_mapping"    : {str(i): lbl for i, lbl in enumerate(LABEL_NAMES)},
        "validation_metrics": metrics.get("validation", {}),
        "test_metrics"     : metrics.get("test", {}),
        "generated_at"     : datetime.utcnow().isoformat() + "Z",
    }
    meta_path = MODELS_DIR / "model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved {meta_path}")

    # ── Metrics CSV ──
    rows = []
    for split, m in metrics.items():
        rows.append({"split": split, **m})
    metrics_df = pd.DataFrame(rows)
    metrics_path = REPORTS_DIR / "model_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"  Saved {metrics_path}")

    # ── Classification report TXT ──
    report_path = REPORTS_DIR / "classification_report.txt"
    with open(report_path, "w") as f:
        f.write("Cybervehicare — Phase 3 Classification Report\n")
        f.write(f"Generated : {datetime.utcnow().isoformat()}Z\n")
        f.write("=" * 60 + "\n\n")
        f.write(report_str)
    print(f"  Saved {report_path}")

    # ── Confusion matrix PNG ──
    fig, ax = plt.subplots(figsize=(7, 6))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=LABEL_NAMES)
    disp.plot(ax=ax, colorbar=True, cmap="Blues", values_format="d")
    ax.set_title(
        "Confusion Matrix — Predictive Maintenance\n(Test Set)",
        fontsize=13, fontweight="bold", pad=12,
    )
    plt.tight_layout()
    cm_path = REPORTS_DIR / "confusion_matrix.png"
    plt.savefig(cm_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {cm_path}")

    # ── Feature importance PNG ──
    importances = clf.feature_importances_
    indices     = np.argsort(importances)[::-1]
    top_n       = min(20, len(feature_cols))
    top_idx     = indices[:top_n]
    top_names   = [feature_cols[i] for i in top_idx]
    top_vals    = importances[top_idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(
        range(top_n), top_vals[::-1],
        color=plt.cm.RdYlGn(np.linspace(0.25, 0.85, top_n)),
        edgecolor="white", linewidth=0.5,
    )
    ax.set_yticks(range(top_n))
    ax.set_yticklabels(top_names[::-1], fontsize=9)
    ax.set_xlabel("Mean Decrease in Impurity (Gini Importance)", fontsize=10)
    ax.set_title(
        f"Top {top_n} Feature Importances — RandomForestClassifier",
        fontsize=13, fontweight="bold", pad=12,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    plt.tight_layout()
    fi_path = REPORTS_DIR / "feature_importance.png"
    plt.savefig(fi_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {fi_path}")


# ─────────────────────────────────────────────
# STEP 6 — INTEGRITY CHECK
# ─────────────────────────────────────────────
def integrity_check() -> None:
    banner("STEP 6 · Integrity Verification")

    expected = [
        MODELS_DIR   / "maintenance_model.pkl",
        MODELS_DIR   / "model_metadata.json",
        MODELS_DIR   / "feature_columns.json",
        REPORTS_DIR  / "model_metrics.csv",
        REPORTS_DIR  / "classification_report.txt",
        REPORTS_DIR  / "confusion_matrix.png",
        REPORTS_DIR  / "feature_importance.png",
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
        print("\n  All Phase 3 artifacts verified ✓")
    else:
        print("\n  WARNING: some files are missing!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "═" * 60)
    print("  CYBERVEHICARE · PHASE 3 — MODEL TRAINING")
    print("  " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    print("═" * 60)

    train_df, val_df, test_df           = load_datasets()
    X_tr, X_v, X_te, y_tr, y_v, y_te, feat_cols = prepare_features(
        train_df, val_df, test_df
    )
    clf                                 = train_model(X_tr, y_tr)
    metrics, report_str, cm             = evaluate(clf, X_v, y_v, X_te, y_te)
    save_artifacts(clf, metrics, report_str, cm, feat_cols)
    integrity_check()

    print("\n" + "═" * 60)
    print("  Phase 3 COMPLETE — Predictive Maintenance Model Trained Successfully")
    print("  Next step → Phase 4: python ml/serve_model.py")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
