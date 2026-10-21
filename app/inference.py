"""Validate feature uploads and call the existing, saved Part I pipeline."""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import io
import sys

import numpy as np
import pandas as pd
import sklearn  # Import the scientific stack before torch on this Windows environment.
import scipy
import joblib
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from preprocessing import (transform_features, mark_invalid_values,
                           recover_missing_power, mask_above_cutoffs,
                           clean_and_engineer_features)
from features import EPOCH_KEY
from crf_model import (SleepStageCRF, build_recording_sequences,
                       convert_sequences_to_tensors, predict_recording_stages)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_ROWS = 100_000
MAX_RECORDING_EPOCHS = 10_000
STAGES = ("W", "N1", "N2", "N3", "REM")


@dataclass
class ModelBundle:
    preprocessor: dict
    model: SleepStageCRF
    stage_to_id: dict
    fingerprint: str

    @property
    def id_to_stage(self):
        return {number: stage for stage, number in self.stage_to_id.items()}


def model_fingerprint():
    """Identify both trusted files without loading a model."""
    paths = [ROOT / "output/preprocessor.joblib", ROOT / "output/final_mlp_crf.pt"]
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Required model file is missing: {path.name}")
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_bundle():
    """Load only the trusted artifacts delivered with this project."""
    fingerprint = model_fingerprint()
    paths = [ROOT / "output/preprocessor.joblib", ROOT / "output/final_mlp_crf.pt"]
    fitted = joblib.load(paths[0])
    checkpoint = torch.load(paths[1], map_location="cpu", weights_only=True)
    if checkpoint["n_features"] != len(fitted["engineered_columns"]):
        raise ValueError("The saved model and preprocessor have different feature counts.")
    mapping = checkpoint["stage_to_id"]
    if set(mapping) != set(STAGES) or set(mapping.values()) != set(range(5)):
        raise ValueError("The saved model has an unexpected stage mapping.")
    torch.set_num_threads(1)
    model = SleepStageCRF(
        checkpoint["n_features"], len(mapping),
        hidden_sizes=checkpoint["params"]["hidden_sizes"],
        dropout=checkpoint["params"]["dropout"],
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return ModelBundle(fitted, model, mapping, fingerprint)


def read_feature_csv(content, feature_columns):
    """Check CSV structure before pandas can rename or shift malformed columns."""
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Choose a non-empty CSV no larger than 100 MiB.")
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("The CSV contains a null character. Export it again as UTF-8 CSV.")
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader)
        if len(header) != len(set(header)):
            raise ValueError("Duplicate column names are not allowed.")
        if len(header) > 100:
            raise ValueError("The CSV has more than 100 columns.")
        # A surplus field can make pandas silently infer an index, shifting
        # participant IDs and measurements. Missing cells need explicit commas.
        rows = 0
        for row in reader:
            if not row:  # Ordinary blank lines have no recording content.
                continue
            if len(row) != len(header):
                raise ValueError(
                    f"CSV row ending at line {reader.line_num} has {len(row)} fields; "
                    f"the header has {len(header)}. Keep a blank cell for missing measurements."
                )
            rows += 1
            if rows > MAX_ROWS:
                raise ValueError("Provide between 1 and 100,000 epoch rows.")
        frame = pd.read_csv(io.StringIO(text), dtype=str, nrows=MAX_ROWS + 1)
    except (UnicodeError, StopIteration, csv.Error,
            pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError("The file must be a readable UTF-8 CSV with a header row.") from exc
    return validate_frame(frame, feature_columns)


def validate_frame(frame, feature_columns):
    """Return a fresh, aligned frame containing only supported input columns."""
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names are not allowed.")
    required = EPOCH_KEY + list(feature_columns)
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if not 0 < len(frame) <= MAX_ROWS:
        raise ValueError("Provide between 1 and 100,000 epoch rows.")
    identifiers = [name for name in ("Row_ID", "Upload_Row_ID") if name in frame]
    result = frame[required + identifiers].copy().reset_index(drop=True)
    for column in ["Subject_ID", "Recording_ID"] + identifiers:
        if result[column].isna().any():
            raise ValueError(f"{column} has a missing identifier.")
        result[column] = result[column].astype(str).str.strip()
        if result[column].eq("").any() or result[column].str.len().gt(128).any():
            raise ValueError(f"{column} identifiers must contain 1-128 characters.")
    epochs = pd.to_numeric(result["Epoch_ID"], errors="coerce")
    if (not np.isfinite(epochs).all() or (epochs % 1 != 0).any()
            or (epochs < 1).any() or (epochs > MAX_RECORDING_EPOCHS).any()):
        raise ValueError("Epoch_ID must be a positive integer, at most 10,000.")
    result["Epoch_ID"] = epochs.astype(int)
    if result.duplicated(EPOCH_KEY).any():
        raise ValueError("Duplicate epoch keys were found in a recording.")
    for identifier in identifiers:
        if result[identifier].duplicated().any():
            raise ValueError(f"{identifier} must be unique within the uploaded file.")
    for _, recording in result.groupby(EPOCH_KEY[:2]):
        ordered = recording["Epoch_ID"].sort_values().to_numpy()
        if not np.array_equal(ordered, np.arange(1, len(ordered) + 1)):
            raise ValueError("Each recording needs consecutive Epoch_ID values starting at 1.")
    if not identifiers:
        result["Upload_Row_ID"] = [f"row-{i + 1}" for i in range(len(result))]
    return result


def predict_frame(frame, bundle):
    """Apply saved settings, decode separate recordings, and retain upload alignment."""
    data = validate_frame(frame, bundle.preprocessor["feature_columns"])
    fitted = bundle.preprocessor
    valid = mark_invalid_values(data, fitted["feature_columns"])
    recovered = recover_missing_power(valid)
    masked = mask_above_cutoffs(recovered, fitted["cutoffs"])
    engineered = clean_and_engineer_features(data, fitted["feature_columns"], fitted["cutoffs"])
    quality = []
    for (subject, recording), rows in data.groupby(EPOCH_KEY[:2]):
        index = rows.index
        if not valid.loc[index].notna().any().any():
            raise ValueError(f"Recording {recording} has no usable original measurements.")
        quality.append({
            "Subject_ID": subject, "Recording_ID": recording, "Epochs": len(rows),
            "Missing or invalid original values": int(valid.loc[index].isna().sum().sum()),
            "Reconstructed original values": int(
                (valid.loc[index].isna() & recovered.loc[index].notna()).sum().sum()),
            "Values above saved cutoffs": int(
                (recovered.loc[index].notna() & masked.loc[index].isna()).sum().sum()),
            "Imputed model inputs": int(engineered.loc[index].isna().sum().sum()),
        })
    # Keep the established transformation function as the single inference path.
    values = transform_features(data, fitted)
    sequences = build_recording_sequences(values, None, data[EPOCH_KEY])
    tensors = convert_sequences_to_tensors(sequences, bundle.stage_to_id)
    stages = predict_recording_stages(bundle.model, tensors, bundle.id_to_stage, batch_size=4)
    id_columns = EPOCH_KEY + [c for c in ("Row_ID", "Upload_Row_ID") if c in data]
    predictions = data[id_columns].copy()
    predictions["Predicted stage"] = stages.reindex(data.index).to_numpy()
    if predictions["Predicted stage"].isna().any():
        raise ValueError("The model did not return a stage for every epoch.")
    return predictions, pd.DataFrame(quality)
