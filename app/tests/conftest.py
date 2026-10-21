"""Generated fixtures only; no assignment recordings are embedded in tests."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.inference import load_bundle


@pytest.fixture(scope="session")
def bundle():
    return load_bundle()


@pytest.fixture
def feature_frame(bundle):
    # Consistent power pairs exercise the real reconstruction rules.
    rows = []
    rng = np.random.default_rng(83)
    for recording, length in [("1", 12), ("2", 9)]:
        for epoch in range(1, length + 1):
            row = {name: float(rng.uniform(0.1, 0.8))
                   for name in bundle.preprocessor["feature_columns"]}
            for band in ["Delta", "Theta", "Alpha", "Sigma", "Beta"]:
                row[f"PSD_Abs_{band}"] = row[f"PSD_Rel_{band}"] * 100
            row.update(Subject_ID="7", Recording_ID=recording, Epoch_ID=epoch,
                       Row_ID=f"{recording}-{epoch}")
            rows.append(row)
    return pd.DataFrame(rows)
