"""ML trainer — PRD Section 3.

Trains classification and regression models for signal prediction.
Supports scikit-learn, LightGBM, and XGBoost.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

import numpy as np
import pandas as pd


@dataclass
class TrainingConfig:
    """Training configuration."""
    model_type: str = "lightgbm"  # lightgbm, xgboost, random_forest, logistic
    target_column: str = "target"
    feature_columns: list[str] = field(default_factory=list)
    train_pct: float = 0.7
    val_pct: float = 0.15
    test_pct: float = 0.15
    random_seed: int = 42
    hyperparams: dict = field(default_factory=dict)


@dataclass
class TrainingResult:
    """Training result with metrics."""
    model_id: str
    model_type: str
    metrics: dict
    feature_importance: dict
    train_size: int
    val_size: int
    test_size: int
    trained_at: str
    config: dict


class MLTrainer:
    """ML model trainer for signal prediction.

    Supports:
    - LightGBM classification/regression
    - XGBoost classification/regression
    - Random Forest
    - Logistic Regression
    """

    def train_classifier(
        self,
        df: pd.DataFrame,
        config: TrainingConfig,
    ) -> TrainingResult:
        """Train a classification model.

        Args:
            df: DataFrame with features and target.
            config: Training configuration.

        Returns:
            TrainingResult with metrics and model info.
        """
        if config.feature_columns:
            features = config.feature_columns
        else:
            features = [c for c in df.columns if c != config.target_column]

        X = df[features].values
        y = df[config.target_column].values

        # Split data
        n = len(df)
        train_end = int(n * config.train_pct)
        val_end = int(n * (config.train_pct + config.val_pct))

        X_train, y_train = X[:train_end], y[:train_end]
        X_val, y_val = X[train_end:val_end], y[train_end:val_end]
        X_test, y_test = X[val_end:], y[val_end:]

        # Train model
        model, metrics, importance = self._train_model(
            X_train, y_train, X_val, y_val, X_test, y_test,
            config.model_type, config.hyperparams, config.random_seed,
        )

        model_id = str(uuid.uuid4())

        return TrainingResult(
            model_id=model_id,
            model_type=config.model_type,
            metrics=metrics,
            feature_importance={f: round(float(i), 4) for f, i in zip(features, importance)},
            train_size=len(X_train),
            val_size=len(X_val),
            test_size=len(X_test),
            trained_at=datetime.utcnow().isoformat(),
            config={
                "model_type": config.model_type,
                "hyperparams": config.hyperparams,
                "seed": config.random_seed,
            },
        )

    def _train_model(
        self,
        X_train, y_train, X_val, y_val, X_test, y_test,
        model_type: str, hyperparams: dict, seed: int,
    ) -> tuple:
        """Train model and return (model, metrics, feature_importance)."""
        if model_type == "lightgbm":
            return self._train_lightgbm(
                X_train, y_train, X_val, y_val, X_test, y_test, hyperparams, seed,
            )
        elif model_type == "xgboost":
            return self._train_xgboost(
                X_train, y_train, X_val, y_val, X_test, y_test, hyperparams, seed,
            )
        elif model_type == "random_forest":
            return self._train_sklearn(
                X_train, y_train, X_val, y_val, X_test, y_test, "random_forest", hyperparams, seed,
            )
        else:
            return self._train_sklearn(
                X_train, y_train, X_val, y_val, X_test, y_test, "logistic", hyperparams, seed,
            )

    def _train_lightgbm(self, X_train, y_train, X_val, y_val, X_test, y_test, params, seed):
        """Train LightGBM classifier."""
        try:
            import lightgbm as lgb
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

            default_params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "verbosity": -1,
                "seed": seed,
                "n_estimators": 100,
                "learning_rate": 0.1,
                "max_depth": 6,
            }
            default_params.update(params)

            model = lgb.LGBMClassifier(**default_params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.log_evaluation(0)],
            )

            y_pred = model.predict(X_test)
            metrics = {
                "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
                "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            }

            importance = model.feature_importances_
            return model, metrics, importance

        except ImportError:
            return self._train_sklearn(
                X_train, y_train, X_val, y_val, X_test, y_test, "random_forest", params, seed,
            )

    def _train_xgboost(self, X_train, y_train, X_val, y_val, X_test, y_test, params, seed):
        """Train XGBoost classifier."""
        try:
            import xgboost as xgb
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

            default_params = {
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "seed": seed,
                "n_estimators": 100,
                "learning_rate": 0.1,
                "max_depth": 6,
            }
            default_params.update(params)

            model = xgb.XGBClassifier(**default_params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            y_pred = model.predict(X_test)
            metrics = {
                "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
                "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            }

            importance = model.feature_importances_
            return model, metrics, importance

        except ImportError:
            return self._train_sklearn(
                X_train, y_train, X_val, y_val, X_test, y_test, "random_forest", params, seed,
            )

    def _train_sklearn(self, X_train, y_train, X_val, y_val, X_test, y_test, model_type, params, seed):
        """Train sklearn model."""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        if model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=params.get("n_estimators", 100),
                max_depth=params.get("max_depth", 10),
                random_state=seed,
            )
        else:
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(random_state=seed, max_iter=1000)

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        metrics = {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        }

        importance = getattr(model, "feature_importances_", np.ones(X_train.shape[1]))
        return model, metrics, importance
