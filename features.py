"""Power ratios and recording-local context for the shared model inputs."""
import pandas as pd

EPOCH_KEY = ["Subject_ID", "Recording_ID", "Epoch_ID"]
CONTEXT_COLUMNS = [
    "PSD_Rel_Delta", "PSD_Rel_Theta", "PSD_Rel_Alpha", "PSD_Rel_Sigma", "PSD_Rel_Beta",
    "Delta_Beta_Ratio", "Alpha_Theta_Ratio", "Sample_Entropy",
]

def add_power_ratios(features):
    """Add delta/beta and alpha/theta ratios while retaining existing features."""
    engineered = features.copy()

    # Compare slow delta activity with faster beta activity.
    # Zero denominators remain missing to avoid division by zero.
    engineered["Delta_Beta_Ratio"] = (
        engineered["PSD_Abs_Delta"]
        / engineered["PSD_Abs_Beta"].where(engineered["PSD_Abs_Beta"] > 0)
    )

    # Compare alpha activity with the slower theta activity.
    engineered["Alpha_Theta_Ratio"] = (
        engineered["PSD_Abs_Alpha"]
        / engineered["PSD_Abs_Theta"].where(engineered["PSD_Abs_Theta"] > 0)
    )

    return engineered

def add_past_epoch_features(features, metadata, columns=CONTEXT_COLUMNS):
    """Add past context without crossing subjects, recordings or missing epochs."""
    if not features.index.is_unique or not features.index.equals(metadata.index):
        raise ValueError("Feature and metadata rows must have identical unique indices.")
    if metadata.duplicated(EPOCH_KEY).any():
        raise ValueError("Duplicate epochs cannot define a temporal sequence.")
    ordered = metadata.sort_values(EPOCH_KEY)
    values = features.loc[ordered.index, columns]
    recording_groups = [ordered["Subject_ID"], ordered["Recording_ID"]]
    steps = ordered.groupby(EPOCH_KEY[:2])["Epoch_ID"].diff()
    # Start a new segment at every recording boundary or gap in epoch numbering.
    segment = steps.ne(1).cumsum()
    groups = recording_groups + [segment]
    previous = values.groupby(groups, sort=False).shift(1)
    rolling = values.groupby(groups, sort=False).transform(
        lambda series: series.rolling(5, min_periods=1).mean()
    )
    engineered = features.copy()
    for column in columns:
        engineered[f"{column}__lag1"] = previous[column].reindex(features.index)
        engineered[f"{column}__change1"] = (
            values[column] - previous[column]
        ).reindex(features.index)
        engineered[f"{column}__mean5"] = rolling[column].reindex(features.index)
    return engineered

def add_recording_context_features(features, metadata, columns=CONTEXT_COLUMNS):
    """Add past, future and centred EEG context without crossing recording boundaries."""
    engineered = add_past_epoch_features(features, metadata, columns=columns)
    ordered = metadata.sort_values(EPOCH_KEY)
    values = features.loc[ordered.index, columns]
    steps = ordered.groupby(EPOCH_KEY[:2])["Epoch_ID"].diff()
    segments = steps.ne(1).cumsum()
    groups = [ordered["Subject_ID"], ordered["Recording_ID"], segments]
    grouped = values.groupby(groups, sort=False)
    following = grouped.shift(-1)

    for column in columns:
        # Future measurements are available for this offline prediction task.
        # The final epoch's unavailable lead remains missing for training-median imputation.
        engineered[f"{column}__lead1"] = following[column].reindex(features.index)

    for window in (5, 15):
        # Five and fifteen epochs cover 2.5 and 7.5 minutes of EEG measurements.
        # At recording edges, use only available observations in the same segment.
        means = grouped.transform(
            lambda series: series.rolling(window, center=True, min_periods=1).mean()
        )
        deviations = grouped.transform(
            lambda series: series.rolling(window, center=True, min_periods=2).std(ddof=0)
        )
        for column in columns:
            engineered[f"{column}__center_mean{window}"] = means[column].reindex(features.index)
            engineered[f"{column}__center_deviation{window}"] = (
                values[column] - means[column]
            ).reindex(features.index)
            engineered[f"{column}__center_std{window}"] = deviations[column].reindex(features.index)
    return engineered
