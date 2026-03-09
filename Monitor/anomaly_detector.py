#!/usr/bin/env python3
"""
Isolation Forest Anomaly Detection Module for NDN Networks
Loads pre-trained model and performs real-time anomaly detection on NDN metrics.
"""

import logging
import json
import os
from pathlib import Path
from typing import Optional, Tuple, Dict
from collections import deque
from datetime import datetime
import numpy as np
import joblib

logger = logging.getLogger(__name__)

# ============================================================================
# Anomaly Detector
# ============================================================================

class IsolationForestAnomalyDetector:
    """
    Real-time Isolation Forest anomaly detector for NDN networks.
    
    Loads pre-trained model and threshold from disk, maintains per-node
    buffers for consecutive measurements, and performs anomaly detection
    with confidence scoring.
    """
    
    def __init__(self, model_dir: str = "../Models", buffer_size: int = 2):
        """
        Initialize the anomaly detector.
        
        Args:
            model_dir: Path to directory containing saved model files
            buffer_size: Number of entries to keep per node (need 2 for delta computation)
        """
        self.model_dir = Path(model_dir)
        self.buffer_size = buffer_size
        self.pipeline = None
        self.threshold = None
        self.feature_cols = None
        self.metadata = None
        self._buffers = {}  # node_name -> deque of recent entries
        
        self._load_model()
        
    def _load_model(self):
        """Load the saved pipeline, threshold, and feature columns."""
        try:
            pipeline_path = self.model_dir / "ndn_isolation_forest.joblib"
            threshold_path = self.model_dir / "ndn_threshold.json"
            features_path = self.model_dir / "feature_cols.json"
            
            if not pipeline_path.exists():
                raise FileNotFoundError(f"Model not found at {pipeline_path}")
            if not threshold_path.exists():
                raise FileNotFoundError(f"Threshold not found at {threshold_path}")
            if not features_path.exists():
                raise FileNotFoundError(f"Feature columns not found at {features_path}")
            
            self.pipeline = joblib.load(str(pipeline_path))
            
            with open(threshold_path, 'r') as f:
                threshold_data = json.load(f)
                self.threshold = threshold_data['threshold']
                self.metadata = threshold_data
            
            with open(features_path, 'r') as f:
                self.feature_cols = json.load(f)
            
            logger.info(f"Loaded Isolation Forest model from {self.model_dir}")
            logger.info(f"Threshold: {self.threshold}")
            logger.info(f"Features: {self.feature_cols}")
            logger.info(f"Trained on {self.metadata['n_training_samples']} samples")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def ingest(self, raw_entry: dict) -> dict:
        """
        Process one raw log entry and return anomaly detection result.
        
        Args:
            raw_entry: Dict with keys like timestamp, node, nPitEntries, etc.
        
        Returns:
            Dict with detection results:
            {
                'node': str,
                'timestamp': str,
                'status': 'buffering' | 'scored' | 'skipped',
                'anomaly_score': float or None,
                'is_anomaly': bool or None,
                'features': dict or None,
                'alert': str (explanation)
            }
        """
        try:
            node = raw_entry.get('node', 'unknown')
            
            # Initialize buffer for new nodes
            if node not in self._buffers:
                self._buffers[node] = deque(maxlen=self.buffer_size)
            
            # Need at least 2 entries to compute deltas (rates)
            if len(self._buffers[node]) < 1:
                # First entry, store and wait for next
                self._buffers[node].append(raw_entry)
                return {
                    'node': node,
                    'timestamp': raw_entry.get('timestamp'),
                    'status': 'buffering',
                    'anomaly_score': None,
                    'is_anomaly': None,
                    'features': None,
                    'alert': 'Warming up - need consecutive measurements'
                }
            
            # Compute features from consecutive entries
            prev_entry = self._buffers[node][-1]
            feature_vector, feature_dict = self._compute_features(prev_entry, raw_entry)
            
            if feature_vector is None:
                self._buffers[node].append(raw_entry)
                return {
                    'node': node,
                    'timestamp': raw_entry.get('timestamp'),
                    'status': 'skipped',
                    'anomaly_score': None,
                    'is_anomaly': None,
                    'features': None,
                    'alert': 'Could not compute features'
                }
            
            # Predict anomaly score
            X = np.array([feature_vector]).reshape(1, -1)
            score = float(self.pipeline.decision_function(X)[0])
            is_anomaly = score < self.threshold
            
            # Prepare normalized score (0-100 scale for UI)
            # Lower scores = more anomalous
            # Convert to percentile-like scale for interpretability
            normalized_score = self._normalize_score(score)
            
            # Update buffer
            self._buffers[node].append(raw_entry)
            
            alert_msg = f"Anomaly score: {score:.6f} ({normalized_score:.1f}%)"
            if is_anomaly:
                alert_msg += " - ANOMALY DETECTED!"
            
            return {
                'node': node,
                'timestamp': raw_entry.get('timestamp'),
                'status': 'scored',
                'anomaly_score': score,
                'normalized_score': normalized_score,
                'is_anomaly': is_anomaly,
                'features': feature_dict,
                'alert': alert_msg
            }
        
        except Exception as e:
            logger.error(f"Error in anomaly detection: {e}")
            return {
                'node': raw_entry.get('node', 'unknown'),
                'timestamp': raw_entry.get('timestamp'),
                'status': 'skipped',
                'anomaly_score': None,
                'is_anomaly': None,
                'features': None,
                'alert': f'Error: {str(e)}'
            }
    
    def _compute_features(self, prev_entry: dict, curr_entry: dict) -> Tuple[Optional[np.ndarray], Optional[Dict]]:
        """
        Compute 10 feature vector from consecutive metric entries.
        
        Returns:
            (feature_array, feature_dict) or (None, None) if computation fails
        """
        try:
            # Extract timestamps and compute delta
            prev_ts_str = prev_entry.get('timestamp', '')
            curr_ts_str = curr_entry.get('timestamp', '')
            
            try:
                prev_time = datetime.fromisoformat(prev_ts_str.replace('Z', '+00:00').split('.')[0])
                curr_time = datetime.fromisoformat(curr_ts_str.replace('Z', '+00:00').split('.')[0])
            except:
                # Fallback for different timestamp formats
                prev_time = datetime.fromisoformat(prev_ts_str.replace('Z', '').split('.')[0])
                curr_time = datetime.fromisoformat(curr_ts_str.replace('Z', '').split('.')[0])
            
            dt = (curr_time - prev_time).total_seconds()
            if dt <= 0:
                return None, None
            
            # Clamp to reasonable minimum (avoid division by very small numbers)
            dt = max(dt, 0.1)
            
            # Absolute features (from current measurement)
            pit_size = float(curr_entry.get('nPitEntries', 0))
            cs_size = float(curr_entry.get('nCsEntries', 0))
            
            # Rate features (delta / seconds)
            pit_diff = float(curr_entry.get('nPitEntries', 0)) - float(prev_entry.get('nPitEntries', 0))
            pit_growth_rate = pit_diff / dt
            
            in_interests_diff = float(curr_entry.get('nInInterests', 0)) - float(prev_entry.get('nInInterests', 0))
            in_interests_rate = in_interests_diff / dt
            
            out_interests_diff = float(curr_entry.get('nOutInterests', 0)) - float(prev_entry.get('nOutInterests', 0))
            out_interests_rate = out_interests_diff / dt
            
            in_data_diff = float(curr_entry.get('nInData', 0)) - float(prev_entry.get('nInData', 0))
            in_data_rate = in_data_diff / dt
            
            nack_diff = (float(curr_entry.get('nInNacks', 0)) + float(curr_entry.get('nOutNacks', 0))) - \
                       (float(prev_entry.get('nInNacks', 0)) + float(prev_entry.get('nOutNacks', 0)))
            nack_rate = nack_diff / dt
            
            # Ratio features (instantaneous from current measurement)
            nHits = float(curr_entry.get('nHits', 0))
            nMisses = float(curr_entry.get('nMisses', 0))
            cache_hit_ratio = nHits / (nHits + nMisses) if (nHits + nMisses) > 0 else 0.0
            
            nSat = float(curr_entry.get('nSatisfiedInterests', 0))
            nUnsat = float(curr_entry.get('nUnsatisfiedInterests', 0))
            satisfaction_ratio = nSat / (nSat + nUnsat) if (nSat + nUnsat) > 0 else 0.0
            unsatisfied_ratio = nUnsat / (nSat + nUnsat) if (nSat + nUnsat) > 0 else 0.0
            
            # Build feature vector in correct order
            features = [
                pit_size,
                pit_growth_rate,
                cs_size,
                cache_hit_ratio,
                satisfaction_ratio,
                unsatisfied_ratio,
                in_interests_rate,
                out_interests_rate,
                in_data_rate,
                nack_rate
            ]
            
            feature_array = np.array(features)
            
            # Create feature dict for logging/debugging
            feature_dict = {col: float(val) for col, val in zip(self.feature_cols, features)}
            
            return feature_array, feature_dict
        
        except Exception as e:
            logger.error(f"Error computing features: {e}")
            return None, None
    
    def _normalize_score(self, score: float) -> float:
        """
        Normalize anomaly score to 0-100 scale for UI.
        
        Lower scores are more anomalous, so we invert.
        This is a heuristic normalization based on typical score ranges.
        """
        try:
            # Typical range: -0.5 to 2.0, threshold near 3.1e-17
            # We'll map to 0-100 where 100 = completely normal, 0 = extremely anomalous
            
            # Shift and scale
            # -0.5 -> ~0%, 2.0 -> ~100%
            normalized = ((score + 0.5) / 2.5) * 100
            # Clamp to 0-100
            normalized = max(0, min(100, normalized))
            return normalized
        except:
            return 50.0  # Default to middle if error


# ============================================================================
# Utility Functions
# ============================================================================

def load_anomaly_detector(model_dir: str = "../Models") -> IsolationForestAnomalyDetector:
    """
    Load and initialize the anomaly detector.
    
    Args:
        model_dir: Path to Models directory
    
    Returns:
        IsolationForestAnomalyDetector instance
    """
    return IsolationForestAnomalyDetector(model_dir)
