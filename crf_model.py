"""Recording sequences, MLP-CRF training, checkpoint recovery and prediction."""
import hashlib
import json
from pathlib import Path
from time import perf_counter

import pandas as pd
from sklearn.metrics import f1_score
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence
from torchcrf import CRF

def build_recording_sequences(features, labels, metadata):
    """Group aligned rows into recordings; labels may be None for test data."""
    ordered = metadata.copy()

    # Preserve each row's position in the feature array before sorting.
    ordered["position"] = range(len(ordered))
    ordered = ordered.sort_values(
        ["Subject_ID", "Recording_ID", "Epoch_ID"]
    )

    sequences = []

    # Build a separate sequence for each recording.
    for _, recording in ordered.groupby(["Subject_ID", "Recording_ID"]):
        positions = recording["position"].to_numpy()

        sequence = {
            "features": features[positions],
            # Retain original row indices to align predictions after decoding.
            "row_indices": recording.index.to_numpy()
        }
        if labels is not None:
            sequence["labels"] = labels.iloc[positions].to_numpy()
        sequences.append(sequence)

    return sequences

def convert_sequences_to_tensors(sequences, stage_to_id):
    """Convert features and any available stage labels into PyTorch tensors."""
    tensor_sequences = []

    for sequence in sequences:
        converted = {
            # Feature measurements require floating-point numbers.
            "features": torch.tensor(
                sequence["features"], dtype=torch.float32
            ),
            # Keep original row indices for aligning decoded predictions.
            "row_indices": sequence["row_indices"]
        }
        if "labels" in sequence:
            # Encode observed labels only; test recordings have no labels.
            label_ids = [stage_to_id[label] for label in sequence["labels"]]
            converted["labels"] = torch.tensor(label_ids, dtype=torch.long)
        tensor_sequences.append(converted)

    return tensor_sequences

def pad_recordings(recordings):
    """Pad a batch of recordings and identify its real epoch positions."""

    # Record the original lengths before padding.
    lengths = torch.tensor([
        len(recording["features"]) for recording in recordings
    ])

    # Extend shorter recordings to the longest recording in this batch.
    features = pad_sequence(
        [recording["features"] for recording in recordings],
        batch_first=True,
        padding_value=0.0
    )
    labels = None
    if all("labels" in recording for recording in recordings):
        labels = pad_sequence(
            [recording["labels"] for recording in recordings],
            batch_first=True,
            padding_value=0
        )
    elif any("labels" in recording for recording in recordings):
        raise ValueError("A batch cannot mix labelled and unlabelled recordings.")

    # Positions below each recording's original length are real epochs.
    positions = torch.arange(features.shape[1])
    mask = positions.unsqueeze(0) < lengths.unsqueeze(1)

    return features, labels, mask

class SleepStageCRF(nn.Module):
    """Per-epoch MLP emission scores followed by a linear-chain CRF."""

    def __init__(self, n_features, n_stages=5, hidden_sizes=(64, 32), dropout=0.1):
        super().__init__()

        # Learn nonlinear feature combinations independently for each epoch.
        layers = []
        input_size = n_features
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            input_size = hidden_size

        # Supply raw stage scores; the CRF handles sequence normalisation.
        layers.append(nn.Linear(input_size, n_stages))
        self.emissions = nn.Sequential(*layers)

        # Learn transition scores between stages within each recording.
        self.crf = CRF(n_stages, batch_first=True)

    def loss(self, features, labels, mask):
        """Calculate negative log-likelihood, averaged across recordings."""
        scores = self.emissions(features)

        # Ignore padded positions when scoring the true label sequences.
        return -self.crf(scores, labels, mask=mask, reduction="mean")

    def predict(self, features, mask):
        """Decode the highest-scoring stage sequence for each recording."""
        scores = self.emissions(features)

        # Viterbi decoding returns predictions for real epochs only.
        return self.crf.decode(scores, mask=mask)

def predict_recording_stages(model, recordings, id_to_stage, batch_size=8):
    """Decode recordings and return stage names indexed by original row IDs."""
    model.eval()
    predictions = []
    row_indices = []

    # Validation uses neither dropout nor gradient calculations.
    with torch.no_grad():
        for start in range(0, len(recordings), batch_size):
            batch = recordings[start:start + batch_size]
            features, _, mask = pad_recordings(batch)
            predicted_sequences = model.predict(features, mask)

            # Decoding excludes padding and preserves each recording's epoch order.
            for recording, predicted_ids in zip(batch, predicted_sequences):
                predictions.extend(id_to_stage[stage_id] for stage_id in predicted_ids)
                row_indices.extend(recording["row_indices"])

    return pd.Series(predictions, index=row_indices, dtype="object")

def predict_emission_stages(model, recordings, stage_to_id):
    """Decode each epoch independently, excluding all CRF transition/start/end scores."""
    id_to_stage = {index: label for label, index in stage_to_id.items()}
    values, indices = [], []
    model.eval()
    with torch.no_grad():
        for recording in recordings:
            predicted_ids = model.emissions(recording["features"]).argmax(dim=-1).tolist()
            values.extend(id_to_stage[index] for index in predicted_ids)
            indices.extend(recording["row_indices"])
    return pd.Series(values, index=indices, dtype="object")

def add_recording_sequences(prepared_folds, stage_to_id):
    """Arrange the shared model inputs into ordered recordings without fitting new transforms."""
    for fold in prepared_folds:
        for subset in ["training", "validation"]:
            sequences = build_recording_sequences(
                fold[f"{subset}_features"], fold[f"{subset}_labels"], fold[f"{subset}_metadata"]
            )
            fold[f"{subset}_sequences"] = sequences
            fold[f"{subset}_tensors"] = convert_sequences_to_tensors(sequences, stage_to_id)


def _save_training_checkpoint(value, path):
    """Replace a checkpoint only after its new contents are fully written."""
    temporary = path.with_suffix('.tmp')
    torch.save(value, temporary)
    temporary.replace(path)

def _validate_checkpoint_inputs(folder, folds, params, checkpoints, stage_to_id, seed):
    """Reject cached training from different data, settings, package versions or source code."""
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    for fold in folds:
        for subset in ["training_tensors", "validation_tensors"]:
            digest.update(subset.encode())
            for recording in fold[subset]:
                for key in ["features", "labels"]:
                    tensor = recording[key].detach().cpu().contiguous()
                    digest.update(str(tuple(tensor.shape)).encode())
                    digest.update(tensor.numpy().tobytes())
                digest.update(json.dumps(list(map(int, recording["row_indices"]))).encode())
    for name in ["features.py", "preprocessing.py", "crf_model.py"]:
        digest.update(Path(__file__).with_name(name).read_bytes())
    manifest = json.loads(json.dumps({
        "fingerprint": digest.hexdigest(), "params": params, "checkpoints": checkpoints,
        "stage_to_id": stage_to_id, "seed": seed, "torch_version": str(torch.__version__),
    }))
    path = folder / "training_manifest.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        for field in ["fingerprint", "params", "stage_to_id", "seed", "torch_version"]:
            if previous[field] != manifest[field]:
                raise ValueError("Training inputs or settings changed. Use a new output directory.")
        if checkpoints[:len(previous["checkpoints"])] != previous["checkpoints"]:
            raise ValueError("Existing checkpoints changed. Use a new output directory.")
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    temporary.replace(path)


def scheduled_learning_rate(params, epoch):
    """Reduce the rate after each specified completed training epoch."""
    reductions = sum(epoch > milestone for milestone in params["lr_milestones"])
    return params["learning_rate"] * params["lr_gamma"] ** reductions

def _restore_training_state(recordings, params, stage_to_id, seed, folder):
    """Initialise reproducibly or restore model, optimizer and random state."""
    torch.manual_seed(seed)
    model = SleepStageCRF(
        recordings[0]["features"].shape[1], n_stages=len(stage_to_id),
        hidden_sizes=params["hidden_sizes"], dropout=params["dropout"],
    )
    optimiser = torch.optim.Adam(
        model.parameters(), lr=params["learning_rate"], weight_decay=params["weight_decay"]
    )
    completed, history = 0, []
    latest = folder / "latest.pt"
    if latest.exists():
        state = torch.load(latest, map_location="cpu", weights_only=True)
        model.load_state_dict(state["model_state"])
        optimiser.load_state_dict(state["optimiser_state"])
        torch.set_rng_state(state["rng_state"])
        completed, history = state["epoch"], state["history"]
    return model, optimiser, completed, history

def _train_one_epoch(model, recordings, optimiser, params, epoch):
    """Update emissions and transitions for one shuffled pass through recordings."""
    model.train()
    learning_rate = scheduled_learning_rate(params, epoch)
    for group in optimiser.param_groups:
        group["lr"] = learning_rate
    order = torch.randperm(len(recordings)).tolist()
    total_loss, largest_norm, clipped, batches = 0.0, 0.0, 0, 0
    for start in range(0, len(order), params["batch_size"]):
        batch = [recordings[index] for index in order[start:start + params["batch_size"]]]
        features, labels, mask = pad_recordings(batch)
        if labels is None:
            raise ValueError("Training requires stage labels.")
        optimiser.zero_grad()
        loss = model.loss(features, labels, mask)
        if not torch.isfinite(loss):
            raise FloatingPointError(f"Non-finite loss at epoch {epoch}.")
        loss.backward()
        # Limit unusually large updates to both emission and transition parameters.
        norm = torch.nn.utils.clip_grad_norm_(
            model.parameters(), params["gradient_clip"], error_if_nonfinite=True
        ).item()
        optimiser.step()
        if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
            raise FloatingPointError(f"Non-finite parameters at epoch {epoch}.")
        total_loss += loss.item() * len(batch)
        largest_norm = max(largest_norm, norm)
        clipped += int(norm > params["gradient_clip"])
        batches += 1
    return {
        "Epoch": epoch, "Loss": total_loss / len(recordings),
        "Learning rate": learning_rate, "Maximum gradient norm": largest_norm,
        "Clipped batches": clipped, "Batches": batches,
    }

def _train_until_epoch(recordings, params, stage_to_id, seed, folder, target, deadline):
    """Continue training to a requested epoch, saving after each complete epoch."""
    folder.mkdir(parents=True, exist_ok=True)
    model, optimiser, completed, history = _restore_training_state(
        recordings, params, stage_to_id, seed, folder
    )
    if completed > target:
        raise ValueError("A requested earlier checkpoint is missing; use intact checkpoints.")
    for epoch in range(completed + 1, target + 1):
        if perf_counter() >= deadline:
            return model, False
        row = _train_one_epoch(model, recordings, optimiser, params, epoch)
        history.append(row)
        _save_training_checkpoint({
            "epoch": epoch, "model_state": model.state_dict(),
            "optimiser_state": optimiser.state_dict(), "rng_state": torch.get_rng_state(),
            "history": history,
        }, folder / "latest.pt")
        pd.DataFrame(history).to_csv(folder / "training_history.csv", index=False)
        if epoch % 10 == 0 or epoch == target:
            print(f"  Epoch {epoch}: loss {row['Loss']:.2f}, LR {row['Learning rate']:.6f}",
                  flush=True)
    return model, True

def evaluate_crf_training_durations(prepared_folds, params, checkpoints, stage_to_id, seed,
                  output_dir, max_hours=8):
    """Evaluate each duration on every subject fold before extending training."""
    if not checkpoints or checkpoints != sorted(set(checkpoints)) or checkpoints[0] < 1:
        raise ValueError("Checkpoints must be increasing positive epoch numbers.")
    folder = Path(output_dir)
    _validate_checkpoint_inputs(folder, prepared_folds, params, checkpoints, stage_to_id, seed)
    deadline = perf_counter() + max_hours * 3600
    # Completing shared checkpoints first permits a fair comparison after a budget stop.
    for target in checkpoints:
        for fold_number, fold in enumerate(prepared_folds, start=1):
            fold_dir = folder / f"fold_{fold_number}"
            path = fold_dir / f"epoch_{target:03d}.pt"
            if path.exists():
                continue
            print(f"Fold {fold_number}/{len(prepared_folds)}: training through epoch {target}",
                  flush=True)
            model, finished = _train_until_epoch(
                fold["training_tensors"], params, stage_to_id, seed, fold_dir, target, deadline
            )
            if not finished:
                print("Time budget reached. Completed epochs are saved; rerun to resume.")
                return read_crf_checkpoint_scores(folder)
            _evaluate_validation_checkpoint(model, fold, stage_to_id, params, fold_number, target, path)
            read_crf_checkpoint_scores(folder).to_csv(folder / "scores.csv", index=False)
    return read_crf_checkpoint_scores(folder)

def fit_final_crf(recordings, params, stage_to_id, seed, output_dir):
    """Refit all labelled recordings using the same schedule as cross-validation."""
    folder = Path(output_dir)
    context = [{"training_tensors": recordings, "validation_tensors": []}]
    _validate_checkpoint_inputs(folder, context, params, [params["epochs"]], stage_to_id, seed)
    model, _ = _train_until_epoch(
        recordings, params, stage_to_id, seed, folder, params["epochs"], float("inf")
    )
    _save_training_checkpoint({
        "state_dict": model.state_dict(), "params": params, "stage_to_id": stage_to_id,
        "n_features": recordings[0]["features"].shape[1],
    }, folder / "final_mlp_crf.pt")
    model.eval()
    return model

def _evaluate_validation_checkpoint(model, fold, stage_to_id, params, fold_number,
                         epoch, path):
    """Save validation predictions, stage scores and the corresponding model weights."""
    id_to_stage = {value: key for key, value in stage_to_id.items()}
    stages = list(stage_to_id)
    predictions = predict_recording_stages(
        model, fold['validation_tensors'], id_to_stage, batch_size=params['batch_size']
    )
    truth = fold['validation_labels']
    scores = f1_score(truth, predictions.loc[truth.index], labels=stages,
                      average=None, zero_division=0)
    row = {
        'Epochs': epoch, 'Fold': fold_number,
        'Macro-F1': float(scores.mean()),
        **{stage: float(score) for stage, score in zip(stages, scores)}
    }
    _save_training_checkpoint({
        'scores': row, 'model_state': model.state_dict(),
        'row_indices': predictions.index.tolist(),
        'predictions': predictions.tolist()
    }, path)
    print(f"  Fold {fold_number}, epoch {epoch}: Macro-F1 = {row['Macro-F1']:.3f}",
          flush=True)

def read_crf_checkpoint_scores(search_dir):
    """Read evaluated checkpoints, including partial trials for progress reporting."""
    rows = []
    for path in sorted(Path(search_dir).glob('fold_*/epoch_*.pt')):
        saved = torch.load(path, map_location='cpu', weights_only=True)
        rows.append(saved['scores'])
    return pd.DataFrame(rows)

def load_crf_fold_models(output_dir, params, epoch, prepared_folds, stage_to_id):
    """Reload the selected common duration and its held-out predictions for every fold."""
    models, predictions, scores = [], [], []
    for number, fold in enumerate(prepared_folds,start=1):
        path = Path(output_dir) / f"fold_{number}" / f"epoch_{epoch:03d}.pt"
        saved = torch.load(path,map_location="cpu",weights_only=True)
        model = SleepStageCRF(
            fold["training_features"].shape[1], len(stage_to_id),
            hidden_sizes=params["hidden_sizes"], dropout=params["dropout"]
        )
        model.load_state_dict(saved["model_state"])
        model.eval()
        models.append(model)
        predictions.append(pd.Series(saved["predictions"],index=saved["row_indices"],dtype="object"))
        scores.append(saved["scores"])
    predictions = pd.concat(predictions)
    if not predictions.index.is_unique:
        raise ValueError("Validation predictions contain overlapping row indices.")
    return models, predictions, pd.DataFrame(scores).set_index("Fold")[["Macro-F1"]+list(stage_to_id)]
