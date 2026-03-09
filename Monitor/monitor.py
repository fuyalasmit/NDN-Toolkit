#!/usr/bin/env python3
"""
NDN Network Monitoring Dashboard Backend
Watches NDN_LOGS directory for metrics, computes metrics, detects anomalies,
and serves data via FastAPI + WebSocket to a real-time dashboard.
"""

import asyncio
import json
import logging
import os
import argparse
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Set
from pathlib import Path
from collections import defaultdict, deque

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from anomaly_detector import load_anomaly_detector

# ============================================================================
# Configuration & Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MetricEntry:
    """Represents a single metrics.jsonl entry with computed values."""
    timestamp: str  # ISO format from log
    node: str
    nPitEntries: int
    nInInterests: int
    nOutInterests: int
    nInData: int
    nInNacks: int
    nOutNacks: int
    nSatisfiedInterests: int
    nUnsatisfiedInterests: int
    nCsEntries: int
    nHits: int
    nMisses: int
    # Computed metrics
    interest_rate: Optional[float] = None
    satisfaction_ratio: Optional[float] = None
    nack_rate: Optional[float] = None
    data_ratio: Optional[float] = None
    cache_hit_ratio: Optional[float] = None
    # Isolation Forest Anomaly Detection
    anomaly_score: Optional[float] = None
    normalized_anomaly_score: Optional[float] = None
    is_anomaly: Optional[bool] = None
    anomaly_confidence: Optional[str] = None


@dataclass
class Alert:
    """Represents a network anomaly alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    node: str = ""
    severity: str = "WARNING"  # WARNING or CRITICAL
    type: str = ""  # e.g., "Interest Flooding Attack", "Cache Poisoning"
    message: str = ""
    acknowledged: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NodeStatus:
    """Represents the current status of a node."""
    name: str
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    has_data: bool = False
    status: str = "idle"  # idle, healthy, warning, critical
    last_metric: Optional[MetricEntry] = None
    metric_history: deque = field(default_factory=lambda: deque(maxlen=100))


# ============================================================================
# Thresholds (Configurable)
# ============================================================================

@dataclass
class AnomalyThresholds:
    """Configurable thresholds for anomaly detection."""
    interest_rate_warning: float = 50.0       # interests/sec
    interest_rate_critical: float = 100.0     # interests/sec
    satisfaction_warning: float = 75.0        # percentage
    satisfaction_critical: float = 50.0       # percentage


# ============================================================================
# Core Monitoring Engine
# ============================================================================

class NDNMonitor:
    """Main monitoring engine for NDN networks."""
    
    def __init__(self, logs_dir: str, models_dir: str = None):
        self.logs_dir = Path(logs_dir)
        self.models_dir = models_dir or Path(__file__).parent.parent / "Models"
        self.nodes: Dict[str, NodeStatus] = {}
        self.alerts: deque = deque(maxlen=50)  # Keep last 50 alerts
        self.thresholds = AnomalyThresholds()
        self.websocket_clients: Set[WebSocket] = set()
        self.file_watchers: Dict[str, float] = {}  # node_name -> last position
        self._discovery_lock = asyncio.Lock()
        
        # Load Isolation Forest anomaly detector
        try:
            self.anomaly_detector = load_anomaly_detector(str(self.models_dir))
            logger.info(f"Loaded Isolation Forest anomaly detector from {self.models_dir}")
        except Exception as e:
            logger.error(f"Failed to load anomaly detector: {e}")
            self.anomaly_detector = None
        
        logger.info(f"Initialized NDN Monitor for logs_dir: {logs_dir}")
    
    async def discover_nodes(self):
        """Discover node folders in NDN_LOGS directory."""
        async with self._discovery_lock:
            if not self.logs_dir.exists():
                logger.warning(f"Logs directory does not exist: {self.logs_dir}")
                await self._broadcast_message("log", f"Logs directory not found: {self.logs_dir}")
                return
            
            try:
                current_nodes = set()
                for item in self.logs_dir.iterdir():
                    if item.is_dir():
                        node_name = item.name
                        current_nodes.add(node_name)
                        
                        if node_name not in self.nodes:
                            self.nodes[node_name] = NodeStatus(name=node_name)
                            logger.info(f"Discovered new node: {node_name}")
                            await self._broadcast_message("node_discovered", {
                                "node": node_name,
                                "discovered_at": self.nodes[node_name].discovered_at
                            })
                            
                            # Load historical data
                            await self._load_node_history(node_name)
                
                # Remove nodes that no longer exist
                removed = set(self.nodes.keys()) - current_nodes
                for node in removed:
                    del self.nodes[node]
                    logger.info(f"Node removed: {node}")
                    
            except Exception as e:
                logger.error(f"Error discovering nodes: {e}")
    
    async def _load_node_history(self, node_name: str):
        """Load all existing metrics from a node's metrics.jsonl file."""
        metrics_file = self.logs_dir / node_name / "metrics.jsonl"
        if not metrics_file.exists():
            logger.info(f"No metrics file found for {node_name}")
            return
        
        try:
            with open(metrics_file, 'r') as f:
                prev_entry = None
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry_data = json.loads(line)
                        entry = self._parse_metric_entry(entry_data)
                        entry = self._compute_metrics(entry, prev_entry)
                        
                        # Run Isolation Forest anomaly detection
                        if self.anomaly_detector:
                            entry = self._run_anomaly_detection(entry, entry_data)
                        
                        self.nodes[node_name].metric_history.append(entry)
                        self.nodes[node_name].last_metric = entry
                        self.nodes[node_name].has_data = True
                        prev_entry = entry
                        
                        # Run legacy anomaly detection
                        await self._check_anomalies(node_name, entry)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Malformed JSON in {node_name}/metrics.jsonl: {e}")
                        continue
            
            logger.info(f"Loaded {len(self.nodes[node_name].metric_history)} historical entries for {node_name}")
            self.nodes[node_name].status = "healthy"
            
        except Exception as e:
            logger.error(f"Error loading history for {node_name}: {e}")
    
    async def tail_metrics(self):
        """Continuously tail new metrics from all nodes."""
        while True:
            await asyncio.sleep(2)  # Poll every 2 seconds
            
            for node_name in list(self.nodes.keys()):
                metrics_file = self.logs_dir / node_name / "metrics.jsonl"
                
                if not metrics_file.exists():
                    continue
                
                try:
                    current_size = metrics_file.stat().st_size
                    last_pos = self.file_watchers.get(node_name, 0)
                    
                    if current_size < last_pos:
                        # File was truncated
                        last_pos = 0
                        self.nodes[node_name].metric_history.clear()
                    
                    with open(metrics_file, 'rb') as f:
                        f.seek(last_pos)
                        
                        while True:
                            line = f.readline()
                            if not line:
                                break
                            
                            try:
                                entry_data = json.loads(line.decode('utf-8').strip())
                                entry = self._parse_metric_entry(entry_data)
                                
                                # Compute metrics against previous entry
                                prev_entry = self.nodes[node_name].last_metric
                                entry = self._compute_metrics(entry, prev_entry)
                                
                                # Run Isolation Forest anomaly detection
                                if self.anomaly_detector:
                                    entry = self._run_anomaly_detection(entry, entry_data)
                                
                                # Store and run detection
                                self.nodes[node_name].metric_history.append(entry)
                                self.nodes[node_name].last_metric = entry
                                self.nodes[node_name].has_data = True
                                self.nodes[node_name].status = "healthy"
                                
                                # Run legacy anomaly detection
                                await self._check_anomalies(node_name, entry)
                                
                                # Broadcast metrics update
                                await self._broadcast_message("metrics", {
                                    "node": node_name,
                                    "entry": self._serialize_entry(entry)
                                })
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"Malformed JSON in {node_name}: {e}")
                                continue
                        
                        self.file_watchers[node_name] = f.tell()
                
                except Exception as e:
                    logger.error(f"Error tailing {node_name} metrics: {e}")
    
    def _parse_metric_entry(self, data: dict) -> MetricEntry:
        """Parse JSON data into MetricEntry."""
        return MetricEntry(
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            node=data.get('node', 'unknown'),
            nPitEntries=data.get('nPitEntries', 0),
            nInInterests=data.get('nInInterests', 0),
            nOutInterests=data.get('nOutInterests', 0),
            nInData=data.get('nInData', 0),
            nInNacks=data.get('nInNacks', 0),
            nOutNacks=data.get('nOutNacks', 0),
            nSatisfiedInterests=data.get('nSatisfiedInterests', 0),
            nUnsatisfiedInterests=data.get('nUnsatisfiedInterests', 0),
            nCsEntries=data.get('nCsEntries', 0),
            nHits=data.get('nHits', 0),
            nMisses=data.get('nMisses', 0)
        )
    
    def _compute_metrics(self, current: MetricEntry, prev: Optional[MetricEntry]) -> MetricEntry:
        """Compute derived metrics from raw values."""
        if prev is None:
            # Not enough data for rate calculations
            return current
        
        try:
            # Parse timestamps to compute time delta (already in ISO format)
            current_time = datetime.fromisoformat(current.timestamp.replace('Z', '').split('.')[0])
            prev_time = datetime.fromisoformat(prev.timestamp.replace('Z', '').split('.')[0])
            time_delta_sec = max((current_time - prev_time).total_seconds(), 0.1)
            
            # Interest rate (interests/sec)
            interest_diff = current.nInInterests - prev.nInInterests
            current.interest_rate = interest_diff / time_delta_sec if time_delta_sec > 0 else 0
            
            # NACK rate
            nack_diff = current.nInNacks - prev.nInNacks
            current.nack_rate = nack_diff / time_delta_sec if time_delta_sec > 0 else 0
            
            # Satisfaction ratio (percentage)
            total_interests = current.nSatisfiedInterests + current.nUnsatisfiedInterests
            if total_interests > 0:
                current.satisfaction_ratio = (current.nSatisfiedInterests / total_interests) * 100
            else:
                current.satisfaction_ratio = 100.0
            
            # Data ratio (in data vs out interests)
            current.data_ratio = current.nInData / max(current.nOutInterests, 1)
            
            # Cache hit ratio (percentage)
            total_cache_access = current.nHits + current.nMisses
            if total_cache_access > 0:
                current.cache_hit_ratio = (current.nHits / total_cache_access) * 100
            else:
                current.cache_hit_ratio = 0.0
            
        except Exception as e:
            logger.warning(f"Error computing metrics: {e}")
        
        return current
    
    def _run_anomaly_detection(self, entry: MetricEntry, raw_data: dict) -> MetricEntry:
        """Run Isolation Forest anomaly detection and update entry."""
        if not self.anomaly_detector:
            return entry
        
        try:
            # Run detection on raw data
            detection_result = self.anomaly_detector.ingest(raw_data)
            
            # Update entry with detection results
            if detection_result['status'] == 'scored':
                entry.anomaly_score = detection_result.get('anomaly_score')
                entry.normalized_anomaly_score = detection_result.get('normalized_score')
                entry.is_anomaly = detection_result.get('is_anomaly', False)
                
                # Set confidence level based on normalized score
                normalized = entry.normalized_anomaly_score or 50
                if normalized > 80:
                    entry.anomaly_confidence = 'LOW'  # Normal
                elif normalized > 50:
                    entry.anomaly_confidence = 'MEDIUM'
                else:
                    entry.anomaly_confidence = 'HIGH'  # Anomalous
                
                logger.debug(f"Anomaly detection for {entry.node}: score={entry.anomaly_score:.6f}, "
                           f"normalized={normalized:.1f}%, is_anomaly={entry.is_anomaly}")
            
        except Exception as e:
            logger.error(f"Error running anomaly detection: {e}")
        
        return entry
    
    async def _check_anomalies(self, node_name: str, entry: MetricEntry):
        """Check for anomalies and create alerts if needed."""
        # Check Isolation Forest anomalies
        if entry.is_anomaly and entry.anomaly_score is not None:
            await self._create_alert(
                node_name, "WARNING", "Isolation Forest Anomaly Detected",
                f"Anomaly score: {entry.anomaly_score:.6f} (threshold: {self.anomaly_detector.threshold:.2e})"
            )
        
        if entry.interest_rate is None:
            return  # Not enough data yet
        
        # Interest Flooding Detection
        if entry.interest_rate > self.thresholds.interest_rate_critical:
            await self._create_alert(
                node_name, "CRITICAL", "Interest Flooding Attack",
                f"Interest rate: {entry.interest_rate:.1f}/sec"
            )
        elif entry.interest_rate > self.thresholds.interest_rate_warning:
            await self._create_alert(
                node_name, "WARNING", "Possible Interest Flooding",
                f"Interest rate: {entry.interest_rate:.1f}/sec"
            )
        
        # Cache Poisoning Detection (Low Satisfaction Ratio)
        if entry.satisfaction_ratio < self.thresholds.satisfaction_critical:
            await self._create_alert(
                node_name, "CRITICAL", "Cache Poisoning / High Drop Rate",
                f"Satisfaction ratio: {entry.satisfaction_ratio:.1f}%"
            )
        elif entry.satisfaction_ratio < self.thresholds.satisfaction_warning:
            await self._create_alert(
                node_name, "WARNING", "Degraded Satisfaction Ratio",
                f"Satisfaction ratio: {entry.satisfaction_ratio:.1f}%"
            )
        
        # Update node status based on alerts
        await self._update_node_status(node_name)
    
    async def _create_alert(self, node: str, severity: str, alert_type: str, message: str):
        """Create an alert (avoid duplicates in short timeframe)."""
        # Check if similar alert already exists (avoid spam)
        now = datetime.utcnow()
        for alert in list(self.alerts)[-10:]:  # Check last 10 alerts
            if (alert.node == node and 
                alert.type == alert_type and 
                (now - alert.created_at).total_seconds() < 10):
                return  # Duplicate alert within 10 seconds
        
        alert = Alert(
            node=node,
            severity=severity,
            type=alert_type,
            message=message
        )
        self.alerts.append(alert)
        logger.warning(f"Alert [{severity}] {node}: {alert_type} - {message}")
        
        await self._broadcast_message("alert", self._serialize_alert(alert))
    
    async def _update_node_status(self, node_name: str):
        """Update node status based on active alerts."""
        node = self.nodes[node_name]
        
        # Check for active critical or warning alerts
        has_critical = any(a.node == node_name and a.severity == "CRITICAL" and not a.acknowledged
                          for a in self.alerts)
        has_warning = any(a.node == node_name and a.severity == "WARNING" and not a.acknowledged
                         for a in self.alerts)
        
        if has_critical:
            node.status = "critical"
        elif has_warning:
            node.status = "warning"
        else:
            node.status = "healthy"
    
    def _serialize_entry(self, entry: MetricEntry) -> dict:
        """Convert MetricEntry to JSON-serializable dict."""
        data = asdict(entry)
        # Ensure all floats are reasonable
        for key in ['interest_rate', 'satisfaction_ratio', 'nack_rate', 'data_ratio']:
            if key in data and data[key] is not None:
                data[key] = round(float(data[key]), 2)
        return data
    
    def _serialize_alert(self, alert: Alert) -> dict:
        """Convert Alert to JSON-serializable dict."""
        return {
            'id': alert.id,
            'timestamp': alert.timestamp,
            'node': alert.node,
            'severity': alert.severity,
            'type': alert.type,
            'message': alert.message,
            'acknowledged': alert.acknowledged
        }
    
    async def _broadcast_message(self, msg_type: str, payload: any):
        """Broadcast message to all connected WebSocket clients."""
        message = json.dumps({
            'type': msg_type,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
        
        disconnected = set()
        for client in self.websocket_clients:
            try:
                await client.send_text(message)
            except Exception as e:
                logger.debug(f"Error broadcasting to client: {e}")
                disconnected.add(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            self.websocket_clients.discard(client)
    
    def get_nodes_list(self) -> list:
        """Get list of all nodes with their status."""
        return [
            {
                'name': node.name,
                'status': node.status,
                'has_data': node.has_data,
                'discovered_at': node.discovered_at,
                'last_metric': self._serialize_entry(node.last_metric) if node.last_metric else None
            }
            for node in self.nodes.values()
        ]
    
    def get_node_history(self, node_name: str, limit: int = 100) -> list:
        """Get historical metrics for a node."""
        if node_name not in self.nodes:
            return []
        return [self._serialize_entry(entry) for entry in self.nodes[node_name].metric_history][-limit:]
    
    def get_active_alerts(self) -> list:
        """Get all active (unacknowledged) alerts."""
        return [self._serialize_alert(a) for a in self.alerts if not a.acknowledged]
    
    def get_all_alerts(self) -> list:
        """Get all alerts."""
        return [self._serialize_alert(a) for a in self.alerts]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def get_thresholds(self) -> dict:
        """Get current anomaly thresholds."""
        return asdict(self.thresholds)
    
    def update_thresholds(self, **kwargs) -> dict:
        """Update anomaly thresholds."""
        for key, value in kwargs.items():
            if hasattr(self.thresholds, key):
                setattr(self.thresholds, key, float(value))
        logger.info(f"Updated thresholds: {kwargs}")
        return asdict(self.thresholds)


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(title="NDN Network Monitor", version="1.0.0")
monitor: Optional[NDNMonitor] = None


@app.on_event("startup")
async def startup_event():
    """Start background tasks on startup."""
    global monitor
    
    # Create monitor instance
    logs_dir = getattr(app.state, 'logs_dir', './NDN_LOGS')
    monitor = NDNMonitor(logs_dir)
    
    # Initial node discovery
    await monitor.discover_nodes()
    
    # Start background tailing task
    asyncio.create_task(monitor.tail_metrics())
    
    # Periodic node discovery (every 10 seconds)
    async def periodic_discovery():
        while True:
            await asyncio.sleep(10)
            await monitor.discover_nodes()
    
    asyncio.create_task(periodic_discovery())
    
    logger.info("NDN Monitor started successfully")


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the dashboard."""
    return FileResponse("static/index.html")


@app.get("/api/nodes")
async def get_nodes():
    """Get list of discovered nodes."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    return {
        'nodes': monitor.get_nodes_list(),
        'count': len(monitor.nodes),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


@app.get("/api/nodes/{node_name}/history")
async def get_node_history(node_name: str, limit: int = 100):
    """Get historical metrics for a node."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    
    history = monitor.get_node_history(node_name, limit)
    if node_name not in monitor.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")
    
    return {
        'node': node_name,
        'entries': history,
        'count': len(history)
    }


@app.get("/api/alerts")
async def get_alerts(include_acknowledged: bool = False):
    """Get alerts (active or all)."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    
    if include_acknowledged:
        alerts = monitor.get_all_alerts()
    else:
        alerts = monitor.get_active_alerts()
    
    return {
        'alerts': alerts,
        'count': len(alerts),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Mark an alert as acknowledged."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    
    if monitor.acknowledge_alert(alert_id):
        await monitor._update_node_status(
            next((a.node for a in monitor.alerts if a.id == alert_id), "")
        )
        return {'success': True, 'alert_id': alert_id}
    else:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    
    return {
        'thresholds': monitor.get_thresholds(),
        'logs_dir': str(monitor.logs_dir)
    }


@app.post("/api/config")
async def update_config(config: dict):
    """Update configuration."""
    if not monitor:
        raise HTTPException(status_code=500, detail="Monitor not initialized")
    
    thresholds = monitor.update_thresholds(**config)
    return {'success': True, 'thresholds': thresholds}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    if not monitor:
        await websocket.close(code=4000, reason="Monitor not initialized")
        return
    
    await websocket.accept()
    monitor.websocket_clients.add(websocket)
    logger.info("WebSocket client connected")
    
    try:
        # Send current state on connection
        await websocket.send_text(json.dumps({
            'type': 'initial_state',
            'payload': {
                'nodes': monitor.get_nodes_list(),
                'alerts': monitor.get_all_alerts(),
                'thresholds': monitor.get_thresholds()
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }))
        
        # Periodic state sync every 5 seconds
        while True:
            await asyncio.sleep(5)
            await websocket.send_text(json.dumps({
                'type': 'state_sync',
                'payload': {
                    'nodes': monitor.get_nodes_list(),
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            }))
    
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        monitor.websocket_clients.discard(websocket)
        logger.info("WebSocket client disconnected")


# ============================================================================
# Serve Static Files
# ============================================================================

app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NDN Network Monitoring Dashboard"
    )
    parser.add_argument(
        '--logs-dir',
        type=str,
        default='./NDN_LOGS',
        help='Path to NDN_LOGS directory (default: ./NDN_LOGS)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to run server on (default: 8000)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    
    args = parser.parse_args()
    
    # Validate logs directory
    logs_path = Path(args.logs_dir)
    if not logs_path.exists():
        logger.warning(f"Logs directory does not exist: {args.logs_dir}")
        logger.info(f"Will watch for creation of: {args.logs_dir}")
    
    # Store logs_dir in app state for startup event
    app.state.logs_dir = args.logs_dir
    
    logger.info(f"Starting NDN Monitor")
    logger.info(f"  Logs directory: {args.logs_dir}")
    logger.info(f"  Server: http://{args.host}:{args.port}")
    logger.info(f"  Dashboard: http://localhost:{args.port}")
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level='info'
    )


if __name__ == '__main__':
    main()
