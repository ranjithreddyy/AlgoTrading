"""Model registry for saving, loading, and comparing trained models."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib

from src.models.baselines import BaseModel


ARTIFACTS_DIR = Path("artifacts/models")


def _git_commit() -> str:
    """Return current git commit hash, or 'unknown'."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


class ModelRegistry:
    """Persist and retrieve trained models with metadata."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else ARTIFACTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def register(
        self,
        name: str,
        model: BaseModel,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a model and its metadata.

        Returns the version string (timestamp-based).
        """
        version = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        model_dir = self.base_dir / name / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        joblib.dump(model, model_dir / "model.joblib")

        # Build metadata
        meta: Dict[str, Any] = metadata.copy() if metadata else {}
        meta.setdefault("name", name)
        meta.setdefault("version", version)
        meta.setdefault("git_commit", _git_commit())
        meta.setdefault("created_at", datetime.utcnow().isoformat())
        meta.setdefault("params", model.get_params())

        # Serialise – convert non-JSON-serialisable values
        with open(model_dir / "metadata.json", "w") as f:
            json.dump(meta, f, indent=2, default=str)

        return version

    # ------------------------------------------------------------------
    def load(self, name: str, version: Optional[str] = None) -> BaseModel:
        """Load a model.  If *version* is None, load the latest."""
        model_root = self.base_dir / name
        if not model_root.exists():
            raise FileNotFoundError(f"No model registered under '{name}'")

        if version is None:
            versions = sorted(os.listdir(model_root))
            if not versions:
                raise FileNotFoundError(f"No versions found for '{name}'")
            version = versions[-1]

        model_path = model_root / version / "model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        return joblib.load(model_path)

    # ------------------------------------------------------------------
    def list_models(self) -> List[Dict[str, Any]]:
        """List all registered models with their latest metadata."""
        entries: List[Dict[str, Any]] = []
        if not self.base_dir.exists():
            return entries

        for name_dir in sorted(self.base_dir.iterdir()):
            if not name_dir.is_dir():
                continue
            for ver_dir in sorted(name_dir.iterdir()):
                meta_path = ver_dir / "metadata.json"
                if meta_path.exists():
                    with open(meta_path) as f:
                        entries.append(json.load(f))
        return entries

    # ------------------------------------------------------------------
    def get_best(self, metric: str = "sharpe") -> Optional[Dict[str, Any]]:
        """Return metadata dict of the best model by *metric*."""
        models = self.list_models()
        if not models:
            return None

        def _score(m: Dict) -> float:
            metrics = m.get("metrics", {})
            return float(metrics.get(metric, float("-inf")))

        return max(models, key=_score)
