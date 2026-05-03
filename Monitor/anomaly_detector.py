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
        self.clip_bounds = {}   # rate-feature clip bounds from training
        self.score_min   = -0.5 # training score range — for display normalization
        self.score_max   =  2.0
        self._buffers    = {}   # node_name -> deque of recent entries
        
        self._load_model()
        
    def _load_model(self):
        """Load the saved pipeline, threshold, feature columns, and clip bounds."""
        try:
            pipeline_path   = self.model_dir / "ndn_isolation_forest.joblib"
            threshold_path  = self.model_dir / "ndn_threshold.json"
            features_path   = self.model_dir / "feature_cols.json"
            clip_bounds_path= self.model_dir / "clip_bounds.json"

            for p in [pipeline_path, threshold_path, features_path]:
                if not p.exists():
                    raise FileNotFoundError(f"Required artifact not found: {p}")

            self.pipeline = joblib.load(str(pipeline_path))

            with open(threshold_path, 'r') as f:
                threshold_data = json.load(f)
                self.threshold = threshold_data['threshold']
                self.metadata  = threshold_data

            with open(features_path, 'r') as f:
                self.feature_cols = json.load(f)

            # Clip bounds are saved by ndn_pipeline.py; fall back gracefully if absent
            if clip_bounds_path.exists():
                with open(clip_bounds_path, 'r') as f:
                    self.clip_bounds = json.load(f)
                logger.info(f"Clip bounds loaded from {clip_bounds_path}")
            else:
                self.clip_bounds = {}
                logger.warning(
                    f"clip_bounds.json not found at {clip_bounds_path}. "
                    "Rate features will not be clipped — retrain with ndn_pipeline.py "
                    "to generate this file."
                )

            # Training score range — used to calibrate the 0-100 display scale.
            # Falls back to hardcoded defaults if the model predates this field.
            self.score_min = threshold_data.get('score_min', -0.5)
            self.score_max = threshold_data.get('score_max',  2.0)

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
        Compute 10-feature vector from two consecutive metric entries.

        All ratio features (cache_hit_ratio, satisfaction_ratio, unsatisfied_ratio)
        are computed from per-interval *deltas*, not cumulative counters.
        This matches engineer_features_pair() in ndn_pipeline.py exactly.

        Returns:
            (feature_array, feature_dict) or (None, None) if computation fails
        """
        try:
            # ── Timestamps & dt ───────────────────────────────────────────────
            prev_ts = prev_entry.get('timestamp', '')
            curr_ts = curr_entry.get('timestamp', '')
            prev_time = datetime.fromisoformat(prev_ts.replace('Z', '').split('.')[0])
            curr_time = datetime.fromisoformat(curr_ts.replace('Z', '').split('.')[0])

            dt = (curr_time - prev_time).total_seconds()
            if dt <= 0:
                return None, None
            dt = max(dt, 0.1)

            # ── Absolute features ─────────────────────────────────────────────
            pit_size = float(curr_entry.get('nPitEntries', 0))
            cs_size  = float(curr_entry.get('nCsEntries',  0))

            # ── Rate features (delta / dt) ────────────────────────────────────
            pit_growth_rate    = (float(curr_entry.get('nPitEntries',  0)) - float(prev_entry.get('nPitEntries',  0))) / dt
            in_interests_rate  = (float(curr_entry.get('nInInterests', 0)) - float(prev_entry.get('nInInterests', 0))) / dt
            out_interests_rate = (float(curr_entry.get('nOutInterests',0)) - float(prev_entry.get('nOutInterests',0))) / dt
            in_data_rate       = (float(curr_entry.get('nInData',      0)) - float(prev_entry.get('nInData',      0))) / dt
            nack_diff = (float(curr_entry.get('nInNacks',  0)) + float(curr_entry.get('nOutNacks',  0))) \
                      - (float(prev_entry.get('nInNacks',  0)) + float(prev_entry.get('nOutNacks',  0)))
            nack_rate = nack_diff / dt

            # ── Ratio features — delta-based (THE FIX) ────────────────────────
            # Old code used cumulative totals (nHits / (nHits + nMisses)).
            # Because nMisses grows monotonically, that ratio drifted over time
            # and diverged from the training distribution → false anomalies.
            # Now we compute from per-interval deltas, matching training.
            d_hits   = float(curr_entry.get('nHits',   0)) - float(prev_entry.get('nHits',   0))
            d_misses = float(curr_entry.get('nMisses', 0)) - float(prev_entry.get('nMisses', 0))
            d_cache  = d_hits + d_misses
            cache_hit_ratio = d_hits / d_cache if d_cache > 0 else 0.0

            d_sat   = float(curr_entry.get('nSatisfiedInterests',   0)) - float(prev_entry.get('nSatisfiedInterests',   0))
            d_unsat = float(curr_entry.get('nUnsatisfiedInterests', 0)) - float(prev_entry.get('nUnsatisfiedInterests', 0))
            d_total = d_sat + d_unsat
            satisfaction_ratio = d_sat   / d_total if d_total > 0 else 0.0
            unsatisfied_ratio  = d_unsat / d_total if d_total > 0 else 0.0

            # ── Build feature vector ──────────────────────────────────────────
            features = [
                pit_size, pit_growth_rate, cs_size,
                cache_hit_ratio, satisfaction_ratio, unsatisfied_ratio,
                in_interests_rate, out_interests_rate, in_data_rate, nack_rate,
            ]

            # ── Apply training-time clip bounds to rate features ──────────────
            rate_cols = ['pit_growth_rate', 'in_interests_rate', 'out_interests_rate',
                         'in_data_rate', 'nack_rate']
            for i, col in enumerate(self.feature_cols):
                if col in rate_cols and col in self.clip_bounds:
                    features[i] = max(self.clip_bounds[col]['lo'],
                                      min(self.clip_bounds[col]['hi'], features[i]))

            feature_array = np.array(features)
            feature_dict  = {col: float(val) for col, val in zip(self.feature_cols, features)}

            return feature_array, feature_dict

        except Exception as e:
            logger.error(f"Error computing features: {e}")
            return None, None
    
    def _normalize_score(self, score: float) -> float:
        """
        Normalize anomaly score to 0-100 scale for UI display.

        Uses the training score distribution so the scale is always calibrated
        to this specific model:
          - score >= threshold  →  30–100%  (green / normal zone)
          - score <  threshold  →   0–30%   (red / anomaly zone)

        The 30% boundary aligns with the dashboard's red-threshold (< 30).
        """
        try:
            thr = self.threshold
            if score >= thr:
                denom = (self.score_max - thr) or 1e-9
                normalized = 30.0 + (score - thr) / denom * 70.0
            else:
                denom = (thr - self.score_min) or 1e-9
                normalized = 30.0 * (score - self.score_min) / denom
            return max(0.0, min(100.0, normalized))
        except Exception:
            return 50.0


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
