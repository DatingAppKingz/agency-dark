"""
Base classes for ML models
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd
from datetime import datetime
import joblib
import json
from pathlib import Path


class BaseMLModel(ABC):
    """Base class for all ML models in the system"""
    
    def __init__(self, model_name: str, version: str = "1.0.0"):
        self.model_name = model_name
        self.version = version
        self.model = None
        self.is_trained = False
        self.training_metadata = {}
        self.feature_names = []
        self.model_path = Path(f"ml/saved_models/{model_name}")
        self.model_path.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Preprocess raw data for model training/prediction"""
        pass
    
    @abstractmethod
    def train(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """Train the model on provided data"""
        pass
    
    @abstractmethod
    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """Make predictions on new data"""
        pass
    
    @abstractmethod
    def evaluate(self, data: pd.DataFrame, y_true: np.ndarray) -> Dict[str, float]:
        """Evaluate model performance"""
        pass
    
    def save_model(self, path: Optional[str] = None) -> str:
        """Save trained model to disk"""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.model_name}_v{self.version}_{timestamp}.pkl"
        
        if path:
            save_path = Path(path) / filename
        else:
            save_path = self.model_path / filename
        
        # Save model
        joblib.dump({
            'model': self.model,
            'feature_names': self.feature_names,
            'training_metadata': self.training_metadata,
            'version': self.version,
            'timestamp': timestamp
        }, save_path)
        
        # Save metadata separately
        metadata_path = save_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump({
                'model_name': self.model_name,
                'version': self.version,
                'timestamp': timestamp,
                'training_metadata': self.training_metadata,
                'feature_names': self.feature_names
            }, f, indent=2)
        
        return str(save_path)
    
    def load_model(self, path: str) -> None:
        """Load trained model from disk"""
        model_data = joblib.load(path)
        
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']
        self.training_metadata = model_data['training_metadata']
        self.is_trained = True
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance if available"""
        if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
            return None
        
        return dict(zip(self.feature_names, self.model.feature_importances_))


class TimeSeriesModel(BaseMLModel):
    """Base class for time series models"""
    
    def __init__(self, model_name: str, version: str = "1.0.0"):
        super().__init__(model_name, version)
        self.time_column = 'date'
        self.frequency = 'D'  # Daily by default
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time series features"""
        df = df.copy()
        
        # Ensure datetime index
        if self.time_column in df.columns:
            df[self.time_column] = pd.to_datetime(df[self.time_column])
            df = df.set_index(self.time_column)
        
        # Basic time features
        df['day_of_week'] = df.index.dayofweek
        df['day_of_month'] = df.index.day
        df['month'] = df.index.month
        df['quarter'] = df.index.quarter
        df['year'] = df.index.year
        df['is_weekend'] = df.index.dayofweek.isin([5, 6]).astype(int)
        
        # Rolling statistics
        for window in [7, 14, 30]:
            df[f'rolling_mean_{window}d'] = df.iloc[:, 0].rolling(window=window, min_periods=1).mean()
            df[f'rolling_std_{window}d'] = df.iloc[:, 0].rolling(window=window, min_periods=1).std()
        
        # Lag features
        for lag in [1, 7, 14, 30]:
            df[f'lag_{lag}d'] = df.iloc[:, 0].shift(lag)
        
        return df
    
    def create_sequences(self, data: np.ndarray, sequence_length: int) -> tuple:
        """Create sequences for time series models"""
        X, y = [], []
        for i in range(len(data) - sequence_length):
            X.append(data[i:i + sequence_length])
            y.append(data[i + sequence_length])
        return np.array(X), np.array(y)


class ClassificationModel(BaseMLModel):
    """Base class for classification models"""
    
    def __init__(self, model_name: str, version: str = "1.0.0"):
        super().__init__(model_name, version)
        self.classes_ = None
        self.class_weights = None
    
    def calculate_class_weights(self, y: np.ndarray) -> Dict[int, float]:
        """Calculate balanced class weights"""
        from sklearn.utils.class_weight import compute_class_weight
        
        classes = np.unique(y)
        weights = compute_class_weight('balanced', classes=classes, y=y)
        return dict(zip(classes, weights))
    
    def predict_proba(self, data: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        if hasattr(self.model, 'predict_proba'):
            X = self.preprocess_data(data)
            return self.model.predict_proba(X)
        else:
            raise NotImplementedError("Model does not support probability predictions")