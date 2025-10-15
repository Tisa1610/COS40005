import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "datasets"
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True, parents=True)

# ---- 1) PE DATASET ----
pe = pd.read_csv(DS / "pe_dataset.csv")

# Drop obvious IDs/text; keep numeric
drop_cols = [c for c in ["FileName", "md5Hash"] if c in pe.columns]
pe = pe.drop(columns=drop_cols, errors="ignore")

# Standardize label: assume 'Benign' exists as 1=benign, 0=malicious
# We want label 0=benign, 1=malicious -> it's already aligned if 'Benign' is 1/0.
if "Benign" in pe.columns:
    pe["label"] = (1 - pe["Benign"]).astype(int)  # 1 becomes 0, 0 becomes 1 (malicious=1)
    pe = pe.drop(columns=["Benign"])

# Keep numeric columns only
pe = pe.select_dtypes(include="number").fillna(0)

pe.to_csv(OUT / "pe_prepared.csv", index=False)
print(f"Saved {OUT/'pe_prepared.csv'} with shape {pe.shape}")

# ---- 2) UGRANSOM (OPTIONAL) ----
# This dataset varies a lot; keep numeric columns and try to standardize a label.
try:
    ug = pd.read_csv(DS / "ugransom.csv")
    # If there is a clear malicious indicator, map it to 0/1 here.
    # Example heuristics (EDIT to match your file):
    label_col = None
    for cand in ["label", "malicious", "is_attack", "attack", "Threats", "Flag"]:
        if cand in ug.columns:
            label_col = cand
            break
    if label_col is None:
        raise RuntimeError("No obvious label column found in UGRansom; edit prepare_datasets.py to map one.")

    # Convert to binary: attempt a generic mapping
    if ug[label_col].dtype.kind in "biu":  # already numeric
        ug["label"] = (ug[label_col] > 0).astype(int)
    else:
        ug["label"] = ug[label_col].astype(str).str.lower().isin(
            ["malicious", "attack", "ransomware", "bad", "1", "true", "yes"]
        ).astype(int)

    ug = ug.drop(columns=[label_col], errors="ignore")
    ug = ug.select_dtypes(include="number").fillna(0)

    ug.to_csv(OUT / "ugransom_prepared.csv", index=False)
    print(f"Saved {OUT/'ugransom_prepared.csv'} with shape {ug.shape}")
except Exception as e:
    print(f"UGRansom not prepared: {e}")
