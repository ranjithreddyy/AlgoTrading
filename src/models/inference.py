"""Model inference utilities."""

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from src.models.baselines import BaseModel
from src.models.model_registry import ModelRegistry


class ModelInference:
    """Load a registered model and produce predictions."""

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self._registry = registry or ModelRegistry()
        self._model: Optional[BaseModel] = None

    def load_model(self, name: str, version: Optional[str] = None) -> None:
        """Load a model from the registry."""
        self._model = self._registry.load(name, version)

    def predict(self, features_df: pd.DataFrame) -> np.ndarray:
        """Return class predictions."""
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")
        return self._model.predict(features_df)

    def predict_with_confidence(
        self, features_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Return (predictions, probabilities)."""
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")
        preds = self._model.predict(features_df)
        probas = self._model.predict_proba(features_df)
        return preds, probas
