"""Small malformed files must fail before any fitted pipeline or model is used."""
import pandas as pd
import pytest

from app.inference import read_feature_csv, validate_frame


@pytest.mark.parametrize("row", [
    "7,1,1,1,999",  # pandas otherwise infers an index and shifts the whole row.
    "7,1,1",        # Missing measurement cells need their delimiter.
])
def test_csv_field_count_cannot_shift_recording_identity(row):
    content = f"Subject_ID,Recording_ID,Epoch_ID,signal\n{row}\n".encode()
    with pytest.raises(ValueError, match="fields"):
        read_feature_csv(content, ["signal"])


@pytest.mark.parametrize("content", [
    b'Subject_ID,Recording_ID,Epoch_ID,signal\n7,1,1,"2"3\n',
    ("x" * 140_000 + "\n").encode(),
    b'Subject_ID,Recording_ID,Epoch_ID,signal\n7,1,1,"unfinished\n',
], ids=["unexpected-quote-tail", "oversize-field", "unfinished-quote"])
def test_malformed_csv_reports_a_validation_error(content):
    with pytest.raises(ValueError, match="readable UTF-8 CSV"):
        read_feature_csv(content, ["signal"])


def test_null_bytes_cannot_silently_truncate_measurements():
    content = b"Subject_ID,Recording_ID,Epoch_ID,signal\n7,1,1,2\x003\n"
    with pytest.raises(ValueError, match="null character"):
        read_feature_csv(content, ["signal"])


def test_explicit_empty_measurements_and_quoted_commas_are_valid():
    content = (b"Subject_ID,Recording_ID,Epoch_ID,signal,extra\n"
               b'7,1,1,,"ignored, extra"\n\n7,1,2,4,unused\n')
    frame = read_feature_csv(content, ["signal"])
    assert frame.Subject_ID.tolist() == ["7", "7"]
    assert frame.Epoch_ID.tolist() == [1, 2]
    assert pd.isna(frame.signal.iloc[0])
    assert frame.signal.iloc[1] == "4"
    assert "extra" not in frame


def test_supplied_upload_row_identifiers_must_be_unique():
    frame = pd.DataFrame({
        "Subject_ID": ["7", "7"], "Recording_ID": ["1", "1"],
        "Epoch_ID": [1, 2], "signal": [2, 3], "Upload_Row_ID": ["same", "same"],
    })
    with pytest.raises(ValueError, match="Upload_Row_ID must be unique"):
        validate_frame(frame, ["signal"])
