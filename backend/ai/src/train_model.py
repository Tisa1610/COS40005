# train_model.py
import json
import joblib
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True, parents=True)

def train_and_save(df: pd.DataFrame, name: str):
    if "label" not in df.columns:
        raise ValueError(f"{name}: missing 'label' column")
    X = df.drop(columns=["label"])
    y = df["label"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    model = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print(f"\n== {name.upper()} ==")
    print(classification_report(y_test, y_pred, digits=4))

    joblib.dump(model, MODELS / f"{name}_model.pkl")
    meta = {
        "feature_names": list(X.columns),
        "label_mean": float(y.mean())
    }
    (MODELS / f"{name}_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Saved: {MODELS / (name + '_model.pkl')} and {MODELS / (name + '_meta.json')}")

# 1) Behavior model
beh_df = pd.read_csv(DATA / "system_data.csv")
needed = ["cpu","file_rate","net_usage","proc_change","avg_entropy",
          "ext_anomaly","reg_mod","thread_rate","label"]
train_and_save(beh_df[needed], "behavior")

# 2) PE static model
pe_df = pd.read_csv(DATA / "pe_prepared.csv")
train_and_save(pe_df, "pe")

# 3) UGRansom model (network flows)
ug_df = pd.read_csv(DATA / "ugransom_prepared.csv")
train_and_save(ug_df, "ugransom")
