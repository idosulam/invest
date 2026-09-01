"""Model registry — PRD Section 8.

Versioned model storage, retrieval, and lifecycle management.
Models are immutable after promotion.
"""

import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from pathlib import Path


@dataclass
class ModelVersion:
    """Registered model version."""
    model_id: str
    name: str
    version: str
    model_type: str
    artifact_path: str
    metrics: dict
    feature_names: list[str]
    training_window: dict
    status: str  # DRAFT, VALIDATED, PROMOTED, ARCHIVED
    created_at: str
    promoted_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ModelRegistry:
    """Model registry for versioned model management.

    Lifecycle: DRAFT → VALIDATED → PROMOTED → ARCHIVED
    Models are immutable after promotion.
    """

    def __init__(self, storage_path: str = "models"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._models: dict[str, ModelVersion] = {}
        self._load_registry()

    def _load_registry(self):
        """Load registry from disk."""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            with open(registry_file) as f:
                data = json.load(f)
                for model_id, model_data in data.items():
                    self._models[model_id] = ModelVersion(**model_data)

    def _save_registry(self):
        """Save registry to disk."""
        registry_file = self.storage_path / "registry.json"
        data = {}
        for model_id, model in self._models.items():
            data[model_id] = {
                "model_id": model.model_id,
                "name": model.name,
                "version": model.version,
                "model_type": model.model_type,
                "artifact_path": model.artifact_path,
                "metrics": model.metrics,
                "feature_names": model.feature_names,
                "training_window": model.training_window,
                "status": model.status,
                "created_at": model.created_at,
                "promoted_at": model.promoted_at,
                "metadata": model.metadata,
            }
        with open(registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def register(
        self,
        name: str,
        model_type: str,
        metrics: dict,
        feature_names: list[str],
        training_window: dict,
        artifact_path: str = "",
        metadata: Optional[dict] = None,
    ) -> ModelVersion:
        """Register a new model version.

        Args:
            name: Model name (e.g., "signal_classifier_v1").
            model_type: Type of model (lightgbm, xgboost, etc.).
            metrics: Training metrics.
            feature_names: List of feature names used.
            training_window: Dict with train start/end dates.
            artifact_path: Path to model artifact.
            metadata: Additional metadata.

        Returns:
            Registered ModelVersion.
        """
        # Determine version
        existing = [m for m in self._models.values() if m.name == name]
        version = f"v{len(existing) + 1}"

        model = ModelVersion(
            model_id=str(uuid.uuid4()),
            name=name,
            version=version,
            model_type=model_type,
            artifact_path=artifact_path,
            metrics=metrics,
            feature_names=feature_names,
            training_window=training_window,
            status="DRAFT",
            created_at=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )

        self._models[model.model_id] = model
        self._save_registry()
        return model

    def get(self, model_id: str) -> Optional[ModelVersion]:
        """Get a model by ID."""
        return self._models.get(model_id)

    def get_latest(self, name: str, status: Optional[str] = None) -> Optional[ModelVersion]:
        """Get latest version of a model by name."""
        candidates = [
            m for m in self._models.values()
            if m.name == name and (status is None or m.status == status)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda m: m.created_at, reverse=True)[0]

    def list_models(self, status: Optional[str] = None) -> list[ModelVersion]:
        """List all registered models."""
        if status:
            return [m for m in self._models.values() if m.status == status]
        return list(self._models.values())

    def promote(self, model_id: str) -> Optional[ModelVersion]:
        """Promote a model to PROMOTED status.

        Only VALIDATED models can be promoted.
        """
        model = self._models.get(model_id)
        if not model:
            return None
        if model.status != "VALIDATED":
            return None

        # Demote any existing promoted model with same name
        for m in self._models.values():
            if m.name == model.name and m.status == "PROMOTED":
                m.status = "ARCHIVED"

        model.status = "PROMOTED"
        model.promoted_at = datetime.utcnow().isoformat()
        self._save_registry()
        return model

    def validate(self, model_id: str) -> Optional[ModelVersion]:
        """Mark a model as VALIDATED."""
        model = self._models.get(model_id)
        if not model or model.status != "DRAFT":
            return None

        model.status = "VALIDATED"
        self._save_registry()
        return model

    def archive(self, model_id: str) -> Optional[ModelVersion]:
        """Archive a model."""
        model = self._models.get(model_id)
        if not model:
            return None

        model.status = "ARCHIVED"
        self._save_registry()
        return model
