# NDN Network Monitoring Dashboard

A professional, real-time monitoring dashboard for Named Data Networking (NDN) networks. This application watches an NDN_LOGS directory, auto-discovers nodes, tails their metrics, computes real-time metrics, detects anomalies using **machine learning (Isolation Forest)**, and displays everything in a polished, interactive web dashboard with alerting capabilities.

## Features

- **Real-time Monitoring**: Live updates via WebSocket every ~5 seconds
- **Auto-Discovery**: Automatically detects new NDN nodes as folders appear in NDN_LOGS
- **ML-Powered Anomaly Detection** ⭐ **NEW**:
  - **Isolation Forest Model**: Pre-trained deep anomaly detector analyzing 10 network features
  - **Real-time Scoring**: Continuous anomaly scoring on live metrics
  - **Color-Coded Zones**:
    - 🟢 Green (60-100%): Normal operation
    - 🟡 Yellow (30-60%): Suspicious behavior
    - 🔴 Red (0-30%): Potential anomaly/attack
  - **Main Dashboard Chart**: Large anomaly score visualization prominently displayed
- **Legacy Anomaly Detection**:
  - Interest Flooding Attack detection
  - Cache Poisoning / High Drop Rate detection
  - Configurable alert thresholds
- **Rich Dashboard**:
  - Node selector with status indicators
  - Real-time metric cards including **ML Anomaly Score**
  - **Large Main Anomaly Chart** (top of dashboard)
  - Time-series charts for trend analysis (last 20 data points)
  - Alert panel with toast notifications
  - Detailed metrics table with color-coding
  - Settings panel for threshold configuration
- **Dark Theme**: Professional monitoring dashboard appearance
- **No Database**: All data kept in memory (last 100 entries per node)
- **Single HTML File Frontend**: Uses Tailwind CSS and Chart.js from CDN (no build step required)

## Tech Stack

- **Backend**: Python 3.8+
  - FastAPI for REST API and WebSocket
  - uvicorn for ASGI server
  - watchdog for file system watching (optional, uses polling fallback)
  - **scikit-learn for ML anomaly detection** ⭐ **NEW**
  - **joblib for model serialization**
- **Frontend**: Single HTML file
  - Tailwind CSS (CDN)
  - Chart.js (CDN)
  - Vanilla JavaScript (no build tools needed)
- **No external database required** — in-memory storage

## Installation

### Prerequisites
- Python 3.8 or higher
- pip or your preferred package manager

### Setup Steps

1. **Clone/Extract the project**:
   ```bash
   cd Monitor
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Quick Start with Test Data (Recommended)

```bash
# Generate test NDN_LOGS with sample metrics for 3 nodes
python setup_test_data.py

# Run the monitor with test data
python monitor.py --logs-dir ./test_NDN_LOGS --port 8000

# Open dashboard: http://localhost:8000
```

The test data includes 3 nodes (node_a, node_b, node_c) with 20 sample metric entries each.

### Basic Usage

Start monitoring the default NDN_LOGS directory:
```bash
python monitor.py
```

The dashboard will be available at: **http://localhost:8000**

### With Custom Options

Specify a custom logs directory and port:
```bash
python monitor.py --logs-dir /path/to/NDN_LOGS --port 8000 --host 0.0.0.0
```

### Available CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--logs-dir` | Path to NDN_LOGS directory | `./NDN_LOGS` |
| `--port` | Port to run server on | `8000` |
| `--host` | Host to bind to | `0.0.0.0` |

### Example with Your Own Data

```bash
# Create NDN_LOGS directory structure with your own metrics
mkdir -p NDN_LOGS/node_a NDN_LOGS/node_b NDN_LOGS/node_c

# Populate with metrics.jsonl files (see Input Data Format section)
# Each metrics.jsonl should contain JSON lines with metric entries

# Run the monitor
python monitor.py --logs-dir ./NDN_LOGS --port 8000

# Open browser to http://localhost:8000
```

## Input Data Format

The application reads from `metrics.jsonl` files in each node subdirectory.

### Directory Structure
```
NDN_LOGS/
├── node_a/
│   └── metrics.jsonl
├── node_b/
│   └── metrics.jsonl
└── node_c/
    └── metrics.jsonl
```

### Metrics Entry Format (JSON Lines)
Each line in `metrics.jsonl` must be valid JSON:

```json
{
  "timestamp": "2026-03-08T06:20:03.063749",
  "node": "node_a",
  "nPitEntries": 3,
  "nInInterests": 228,
  "nOutInterests": 219,
  "nInData": 160,
  "nInNacks": 1,
  "nOutNacks": 4,
  "nSatisfiedInterests": 158,
  "nUnsatisfiedInterests": 7,
  "nCsEntries": 114,
  "nHits": 0,
  "nMisses": 212
}
```

## Computed Metrics

The backend automatically computes the following derived metrics from raw values:

### Interest Rate (interests/sec)
```
interest_rate = (current.nInInterests - previous.nInInterests) / time_delta
```
Requires at least 2 entries to compute.

### Satisfaction Ratio (%)
```
total_interests = nSatisfiedInterests + nUnsatisfiedInterests
satisfaction_ratio = (nSatisfiedInterests / total_interests) * 100
```

### NACK Rate (nacks/sec)
```
nack_rate = (current.nInNacks - previous.nInNacks) / time_delta
```

### PIT Utilization
Raw value: `nPitEntries` — indicator of network congestion

### Data Ratio
```
data_ratio = nOutData / max(nInData, 1)
```

## Anomaly Detection

The system monitors for network attacks and issues based on configurable thresholds.

### 1. Interest Flooding Attack

**What it detects**: Unusually high rate of incoming interests, potentially indicating a DDoS attack.

**Default Thresholds**:
- ⚠️ **WARNING**: Interest rate > 50 interests/sec
- 🔴 **CRITICAL**: Interest rate > 100 interests/sec

**How it works**:
- Computes the rate of change in `nInInterests` per second
- Compares against configurable thresholds
- Triggers alerts when threshold exceeded

### 2. Cache Poisoning / High Drop Rate

**What it detects**: Low satisfaction ratio indicating either poisoned cache or high packet loss/drops.

**Default Thresholds**:
- ⚠️ **WARNING**: Satisfaction ratio < 75%
- 🔴 **CRITICAL**: Satisfaction ratio < 50%

**How it works**:
- Calculates `satisfaction_ratio = nSatisfiedInterests / (nSatisfiedInterests + nUnsatisfiedInterests)`
- Compares against configurable thresholds
- Triggers alerts when ratio drops below threshold

### Alert Object Schema

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-31T10:15:43.778000Z",
  "node": "node_a",
  "severity": "CRITICAL",
  "type": "Interest Flooding Attack",
  "message": "Interest rate: 143.5/sec",
  "acknowledged": false
}
```

### Alert Lifecycle

- **New alerts**: Appear as toast notifications at top-right
- **Active alerts**: Listed in the persistent alerts panel
- **Auto-clear**: WARNING alerts auto-clear after 30 seconds if conditions improve
- **Manual acknowledge**: User clicks [ACK] button to acknowledge
- **CRITICAL alerts**: Stay until manually acknowledged by user
- **Storage**: Last 50 alerts kept in memory

## Dashboard UI

### Main Components

#### Header
- **Status Indicator**: Green pulsing dot when connected, red when disconnected
- **Alert Bell**: Shows count of unacknowledged alerts
- **Settings Button**: Open configuration modal
- **Node Counter**: Shows number of discovered nodes
- **Last Update**: Shows time since last metric update

#### Node Selector
- **All Nodes**: View aggregate metrics across all nodes
- **Individual Nodes**: Click to filter dashboard to single node
- **Status Badges**: Color-coded indicators (● healthy, ⚠ warning, 🔴 critical)

#### Metrics Cards (4 cards)
- Interest Rate (interests/sec)
- Satisfaction Ratio (%)
- PIT Size (pending interests)
- CS Entries (cache size)

Color-coded based on thresholds:
- 🟢 Green: Normal
- 🟡 Yellow: Warning threshold exceeded
- 🔴 Red: Critical threshold exceeded

#### Time Series Charts (4 charts)
All show last 20 data points with smooth animations:
- **Interest Rate Over Time**: Trends in incoming interest packets
- **Satisfaction Ratio Over Time**: Cache hit/satisfaction trends
- **PIT Size Over Time**: Network congestion indicator
- **NACK Rate Over Time**: Negative acknowledgements rate

Each selected node appears as a colored line:
- Charts auto-update on new WebSocket data
- Interactive legend to show/hide lines (click legend items)

#### Alerts Panel
- Lists all active (unacknowledged) alerts
- Color-coded by severity (red for CRITICAL, yellow for WARNING)
- Shows timestamp, node name, alert type, and message
- [ACK] button to acknowledge
- [Clear All] button (when alerts present)

#### Metrics Table
Sortable table showing latest metrics for all nodes:
- Columns: Node, Status, Uptime, Interest Rate, Satisfaction %, PIT Size, CS Entries, In Interests, Out Interests
- Color-coded cells based on thresholds
- Hover effects for readability

#### Settings Modal
Configure anomaly detection thresholds:
- Interest Rate Warning Threshold (default: 50 int/sec)
- Interest Rate Critical Threshold (default: 100 int/sec)
- Satisfaction Warning Threshold (default: 75%)
- Satisfaction Critical Threshold (default: 50%)
- Display current logs directory path (read-only)
- Changes apply immediately to anomaly detection

### Visual Design
- **Dark Theme**: Slate-900 background with slate-800 cards
- **Color Scheme**:
  - 🔵 Blue (#3b82f6): Normal/healthy metrics
  - 🟢 Green (#22c55e): Healthy status
  - 🟡 Amber (#eab308): Warning alerts
  - 🔴 Red (#ef4444): Critical alerts
- **Fonts**: System UI fonts, monospace for metric values
- **Animations**: Smooth transitions, pulsing indicators, slide-in alerts
- **Responsive**: Works on desktop and tablets

## REST API Reference

### Endpoints

#### Nodes
```
GET /api/nodes
```
Returns list of discovered nodes with their status and last metric.

**Response**:
```json
{
  "nodes": [
    {
      "name": "node_a",
      "status": "healthy",
      "has_data": true,
      "discovered_at": "2026-01-31T10:15:43.778000Z",
      "last_metric": { ... }
    }
  ],
  "count": 3,
  "timestamp": "2026-01-31T10:15:43.778000Z"
}
```

#### Node History
```
GET /api/nodes/{node_name}/history?limit=100
```
Returns historical metrics for a node (last 100 by default, max configurable).

**Response**:
```json
{
  "node": "node_a",
  "entries": [ ... ],
  "count": 100
}
```

#### Alerts
```
GET /api/alerts?include_acknowledged=false
```
Returns active or all alerts.

**Response**:
```json
{
  "alerts": [ ... ],
  "count": 3,
  "timestamp": "2026-01-31T10:15:43.778000Z"
}
```

#### Acknowledge Alert
```
POST /api/alerts/{alert_id}/acknowledge
```
Mark an alert as acknowledged.

#### Configuration
```
GET /api/config
```
Get current thresholds and logs directory.

```
POST /api/config
```
Update thresholds.

**Request Body**:
```json
{
  "interest_rate_warning": 50.0,
  "interest_rate_critical": 100.0,
  "satisfaction_warning": 75.0,
  "satisfaction_critical": 50.0
}
```

#### WebSocket
```
WS /ws
```
Real-time updates via WebSocket connection.

**Message Types**:
- `initial_state`: Sent on connect with current state
- `state_sync`: Periodic sync every 5 seconds
- `metrics`: New metric entries
- `alert`: New alerts
- `node_discovered`: Node discovered
- `log`: Server log messages

## Troubleshooting

### Dashboard shows "No nodes found"
- Ensure NDN_LOGS directory exists
- Check that node subdirectories exist (e.g., `NDN_LOGS/node_a/`)
- Verify `metrics.jsonl` file exists in at least one node directory

### Charts are empty
- Charts populate from historical data on first connection
- Check that metrics.jsonl contains valid JSON lines
- Ensure timestamps in metrics are recent

### WebSocket disconnects frequently
- Check network connectivity
- Verify backend is running: `curl http://localhost:8000`
- Check browser console for specific errors
- Automatic reconnection should occur every 3 seconds

### Alerts not appearing
- Verify metrics are being written to metrics.jsonl
- Check that interest_rate is being computed (requires 2+ entries)
- Open Settings modal to verify thresholds
- Check browser DevTools console for errors

### "Logs directory not found" error
- Ensure the path passed to `--logs-dir` is correct
- Use absolute paths for clarity: `python monitor.py --logs-dir /home/user/NDN_LOGS`
- Directory doesn't need to exist initially, but must be created before nodes are discovered

## File Structure

```
Monitor/
├── monitor.py              # FastAPI backend [~700 lines]
├── setup_test_data.py      # Test data generator - quickly create sample metrics
├── requirements.txt        # Python dependencies
├── static/
│   └── index.html          # Complete frontend dashboard [~1150 lines]
└── README.md              # This file

Generated on first run:
└── test_NDN_LOGS/         # Sample test data (created by setup_test_data.py)
    ├── node_a/
    │   └── metrics.jsonl
    ├── node_b/
    │   └── metrics.jsonl
    └── node_c/
        └── metrics.jsonl
```

## Performance Considerations

- **Memory**: Last 100 metrics per node kept in memory
- **Data Push**: WebSocket updates every 5 seconds (configurable in code)
- **File Polling**: Checks for new metrics every 2 seconds
- **Scalability**: Tested with 10+ nodes, can handle 100+ with tuning

## Development & Customization

### Extending Anomaly Detection

To add a new anomaly type, edit `monitor.py`:

1. Add detection logic in `NDNMonitor._check_anomalies()`
2. Call `await self._create_alert()` with appropriate severity
3. (Optional) Add UI color-coding in `static/index.html`

Example:
```python
# In _check_anomalies()
if metric.nack_rate > 10.0:
    await self._create_alert(
        node_name, "WARNING", "High NACK Rate",
        f"NACK rate: {metric.nack_rate:.1f}/sec"
    )
```

### Changing Update Frequency

- **WebSocket updates**: Line in `websocket_endpoint()` (currently 5 seconds)
- **File polling**: Line in `tail_metrics()` (currently 2 seconds)
- **Node discovery**: Line in `startup_event()` (currently 10 seconds)

### Modifying Thresholds

Default thresholds in `monitor.py`:
```python
self.thresholds = AnomalyThresholds(
    interest_rate_warning=50.0,
    interest_rate_critical=100.0,
    satisfaction_warning=75.0,
    satisfaction_critical=50.0
)
```

Can also be changed via Settings panel in UI.

## License

This project is provided as-is for educational and monitoring purposes.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Verify logs directory structure
3. Check browser DevTools console for frontend errors
4. Check backend logs (`python monitor.py` output) for server errors

---

**Version**: 1.0.0  
**Last Updated**: January 31, 2026  
**Python Required**: 3.8+
