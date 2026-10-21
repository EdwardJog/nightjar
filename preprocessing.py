"""Shared training-only preprocessing for logistic regression and the CRF."""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from features import EPOCH_KEY, add_power_ratios, add_recording_context_features

def mark_invalid_values(data, feature_columns):
    """Return numeric EEG features with invalid measurements marked as missing."""

    # Select EEG predictors and convert malformed text to missing values.
    cleaned = data[feature_columns].apply(pd.to_numeric, errors="coerce")

    # Replace known error codes and infinite measurements.
    cleaned = cleaned.replace(
        [-9999, float("inf"), float("-inf")],
        float("nan")
    )

    # Apply physical validity rules across feature families.
    for column in cleaned.columns:
        if column.startswith("PSD_Rel_"):
            # Relative power must lie between zero and one.
            cleaned[column] = cleaned[column].where(
                cleaned[column].between(0, 1)
            )

        elif column.startswith("PSD_Abs_") or column.endswith("_InstEnergy"):
            # Absolute power and instantaneous energy cannot be negative.
            cleaned[column] = cleaned[column].where(
                cleaned[column] >= 0
            )

    return cleaned

def recover_missing_power(features, tolerance=1e-6):
    """Recover missing power values from agreeing bands within the same epoch."""
    reconstructed = features.copy()

    # Identify absolute-power columns with a corresponding relative-power column.
    bands = [
        column.removeprefix("PSD_Abs_")
        for column in features.columns
        if column.startswith("PSD_Abs_")
        and column.replace("PSD_Abs_", "PSD_Rel_") in features.columns
    ]

    # Estimate total power from each intact, positive absolute/relative pair.
    totals = pd.DataFrame(index=features.index)

    for band in bands:
        absolute = features[f"PSD_Abs_{band}"]
        relative = features[f"PSD_Rel_{band}"]

        totals[band] = absolute.where(absolute > 0) / relative.where(relative > 0)

    for band in bands:
        absolute_column = f"PSD_Abs_{band}"
        relative_column = f"PSD_Rel_{band}"

        # Use other bands so the damaged pair cannot influence its own recovery.
        other_totals = totals.drop(columns=band)
        total = other_totals.median(axis=1)
        spread = (other_totals.max(axis=1) - other_totals.min(axis=1)) / total

        # Require at least two independent band estimates that agree.
        reliable = (
            (other_totals.notna().sum(axis=1) >= 2)
            & (spread <= tolerance)
        )

        # Recover absolute power from a valid relative power and reliable total.
        recovered_absolute = features[relative_column] * total
        recover_absolute = (
            features[absolute_column].isna()
            & reliable
            & recovered_absolute.ge(0)
        )
        reconstructed.loc[recover_absolute, absolute_column] = (
            recovered_absolute[recover_absolute]
        )

        # Recover relative power only when the result remains within [0, 1].
        recovered_relative = features[absolute_column] / total
        recover_relative = (
            features[relative_column].isna()
            & reliable
            & recovered_relative.between(0, 1)
        )
        reconstructed.loc[recover_relative, relative_column] = (
            recovered_relative[recover_relative]
        )

    return reconstructed

def fit_upper_iqr_cutoffs(features, columns, multiplier=10):
    """Calculate upper IQR cutoffs for selected features using training data."""

    # Calculate a separate cutoff for each selected feature.
    selected = features[columns]
    q1 = selected.quantile(0.25)
    q3 = selected.quantile(0.75)

    return q3 + multiplier * (q3 - q1)

def mask_above_cutoffs(features, cutoffs):
    """Replace values above the supplied cutoffs with missing values."""
    masked = features.copy()

    # Apply each cutoff to its corresponding feature.
    for column, cutoff in cutoffs.items():
        masked[column] = masked[column].where(
            masked[column] <= cutoff
        )

    return masked

def clean_and_engineer_features(data, feature_columns, cutoffs):
    """Apply fixed validity rules, saved cutoffs and deterministic recording-local features."""
    cleaned = recover_missing_power(mark_invalid_values(data, feature_columns))
    cleaned = mask_above_cutoffs(cleaned, cutoffs)
    return add_recording_context_features(add_power_ratios(cleaned), data[EPOCH_KEY])


def fit_preprocessor(training, feature_columns, cutoff_columns, multiplier=10):
    """Learn cutoffs, feature medians and standardisation from training rows only."""
    cleaned = recover_missing_power(mark_invalid_values(training, feature_columns))
    cutoffs = fit_upper_iqr_cutoffs(cleaned, cutoff_columns, multiplier)
    features = add_recording_context_features(
        add_power_ratios(mask_above_cutoffs(cleaned, cutoffs)), training[EPOCH_KEY]
    )
    imputer = SimpleImputer(strategy="median")
    values = imputer.fit_transform(features)
    if values.shape[1] != features.shape[1]:
        raise ValueError("A training feature has no valid values for median imputation.")
    imputed = pd.DataFrame(values, index=training.index, columns=features.columns)
    scaler = StandardScaler()
    transformed = scaler.fit_transform(imputed)
    if not np.isfinite(transformed).all():
        raise ValueError("Preprocessing produced non-finite model inputs.")
    fitted = {
        "feature_columns": list(feature_columns), "engineered_columns": features.columns.tolist(),
        "cutoffs": cutoffs, "imputer": imputer, "scaler": scaler,
    }
    return transformed, fitted


def transform_features(data, fitted):
    """Use the saved training cutoffs, medians and scales for validation or test recordings."""
    features = clean_and_engineer_features(data, fitted["feature_columns"], fitted["cutoffs"])
    features = features[fitted["engineered_columns"]]
    imputed = pd.DataFrame(
        fitted["imputer"].transform(features), index=data.index, columns=features.columns
    )
    transformed = fitted["scaler"].transform(imputed)
    if not np.isfinite(transformed).all():
        raise ValueError("Preprocessing produced non-finite model inputs.")
    return transformed


def prepare_shared_folds(data, folds, feature_columns, cutoff_columns, multiplier=10):
    """Prepare one set of training/validation inputs for both models in each subject fold."""
    prepared = []
    for training_indices, validation_indices in folds:
        training, validation = data.iloc[training_indices], data.iloc[validation_indices]
        if set(training["Subject_ID"]) & set(validation["Subject_ID"]):
            raise ValueError("Training and validation subjects overlap.")
        values, fitted = fit_preprocessor(training, feature_columns, cutoff_columns, multiplier)
        fold = {"preprocessor": fitted}
        for subset, rows, transformed in [
            ("training", training, values),
            ("validation", validation, transform_features(validation, fitted)),
        ]:
            fold[f"{subset}_features"] = transformed
            fold[f"{subset}_labels"] = rows["Sleep Stage"]
            fold[f"{subset}_metadata"] = rows[EPOCH_KEY].copy()
        prepared.append(fold)
    return prepared
