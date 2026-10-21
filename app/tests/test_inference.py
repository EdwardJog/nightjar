import numpy as np
import pandas as pd
import pytest

from app.inference import read_feature_csv, validate_frame, predict_frame
from crf_model import (build_recording_sequences, convert_sequences_to_tensors,
                       predict_recording_stages)
from features import EPOCH_KEY
from preprocessing import transform_features


def test_schema_and_csv_validation(feature_frame, bundle):
    columns = bundle.preprocessor["feature_columns"]
    result = read_feature_csv(feature_frame.to_csv(index=False).encode(), columns)
    assert len(result) == 21
    with pytest.raises(ValueError, match="Missing required"):
        validate_frame(feature_frame.drop(columns=columns[0]), columns)
    with pytest.raises(ValueError, match="Duplicate column"):
        read_feature_csv(b"Subject_ID,Subject_ID\n7,7\n", columns)
    with pytest.raises(ValueError, match="consecutive"):
        validate_frame(feature_frame.drop(index=3), columns)
    with pytest.raises(ValueError, match="Duplicate epoch"):
        validate_frame(pd.concat([feature_frame, feature_frame.iloc[:1]]), columns)
    with pytest.raises(ValueError, match="identifier"):
        validate_frame(feature_frame.assign(Subject_ID=" "), columns)
    with pytest.raises(ValueError, match="integer"):
        validate_frame(feature_frame.assign(Epoch_ID=1.5), columns)
    with pytest.raises(ValueError, match="Row_ID"):
        validate_frame(feature_frame.assign(Row_ID="same"), columns)


def test_real_inference_matches_existing_pipeline_and_shuffle(feature_frame, bundle, monkeypatch):
    data = validate_frame(feature_frame, bundle.preprocessor["feature_columns"])
    transformed = transform_features(data, bundle.preprocessor)
    sequences = build_recording_sequences(transformed, None, data[EPOCH_KEY])
    tensors = convert_sequences_to_tensors(sequences, bundle.stage_to_id)
    expected = predict_recording_stages(bundle.model, tensors, bundle.id_to_stage)
    # Fitting must never occur through the application inference path.
    def forbidden(*args, **kwargs):
        raise AssertionError("An upload must not fit preprocessing.")
    monkeypatch.setattr(bundle.preprocessor["imputer"], "fit", forbidden)
    monkeypatch.setattr(bundle.preprocessor["scaler"], "fit", forbidden)
    predicted, quality = predict_frame(data.assign(**{"Sleep Stage": "WRONG"}), bundle)
    assert predicted["Predicted stage"].tolist() == expected.reindex(data.index).tolist()
    assert len(predicted) == 21
    assert set(predicted["Predicted stage"]) <= {"W", "N1", "N2", "N3", "REM"}
    assert quality["Epochs"].sum() == 21
    shuffled, _ = predict_frame(data.sample(frac=1, random_state=9), bundle)
    pd.testing.assert_series_equal(
        predicted.set_index("Row_ID")["Predicted stage"].sort_index(),
        shuffled.set_index("Row_ID")["Predicted stage"].sort_index())
    # A recording's result cannot depend on another recording in the upload.
    alone, _ = predict_frame(data[data.Recording_ID == "2"], bundle)
    assert alone["Predicted stage"].tolist() == predicted.loc[
        predicted.Recording_ID == "2", "Predicted stage"].tolist()


def test_cleaning_and_completely_invalid_recording(feature_frame, bundle):
    frame = feature_frame.copy()
    frame.loc[0, "PSD_Abs_Alpha"] = -9999
    predictions, quality = predict_frame(frame, bundle)
    assert quality["Reconstructed original values"].sum() == 1
    assert len(predictions) == len(frame)
    frame[bundle.preprocessor["feature_columns"]] = np.nan
    with pytest.raises(ValueError, match="no usable"):
        predict_frame(frame, bundle)


def test_optional_row_id_and_extra_columns(feature_frame, bundle):
    frame = validate_frame(feature_frame.drop(columns="Row_ID").assign(secret="ignored"),
                           bundle.preprocessor["feature_columns"])
    assert frame["Upload_Row_ID"].is_unique
    assert "secret" not in frame
