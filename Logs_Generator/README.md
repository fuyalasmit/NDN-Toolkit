# NDN Node Logging Simulator

A Python application that simulates Named Data Networking (NDN) nodes and generates realistic metrics logs in JSONL format. Supports multiple simulation modes including attack simulations (interest flooding, cache poisoning).

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Basic Usage (Normal Mode)
```bash
python generator.py
```

This starts 5 nodes (node_a through node_e) in normal mode, logging metrics every 5 seconds to `NDN_LOGS/`.

### Run Custom Nodes
```bash
python generator.py --nodes node_1,node_2,node_3 --output-dir ./my_logs
```

## Simulation Modes

### 1. Normal Mode (Default)
All nodes behave normally with realistic metric ranges.

```bash
python generator.py --mode normal
```

**Characteristics:**
- Interest rate: ~0.5–2 per second
- Satisfaction ratio: 90–96%
- Cache steady growth
- Rare NACKs

### 2. Interest Flooding Attack
One or more nodes receive a sudden spike in incoming interests (>100/sec), with low satisfaction ratio (<50%).

```bash
# Attack node_a
python generator.py --mode flooding --attack-nodes node_a

# Attack multiple nodes
python generator.py --mode flooding --attack-nodes node_a,node_c
```

**Characteristics:**
- Interest rate: 50–120 per second
- Satisfaction ratio: 15–35%
- Low data response rate
- PIT entries spike
- Starts after default 60 seconds

### 3. Cache Poisoning Attack
One or more nodes show abnormally fast cache growth with low satisfaction ratio and poor cache hit rates.

```bash
# Attack node_b
python generator.py --mode poisoning --attack-nodes node_b

# Attack multiple nodes
python generator.py --mode poisoning --attack-nodes node_a,node_b,node_d
```

**Characteristics:**
- Cache growth: 15–40 entries per tick
- Satisfaction ratio: drops below 50%
- Cache hit ratio: <10%
- Starts after default 60 seconds

### 4. Mixed Mode
Some nodes are under attack, others operate normally. Great for testing monitoring systems.

```bash
# node_a under flooding attack, others normal
python generator.py --mode mixed --attack-nodes node_a

# node_a flooding, node_b cache poisoning
python generator.py --mode mixed --attack-nodes node_a,node_b
```

## Command-Line Options

```
Options:
  --output-dir PATH         Path to NDN_LOGS folder (default: ./NDN_LOGS)
  --nodes TEXT              Comma-separated node names (default: node_a,node_b,node_c,node_d,node_e)
  --interval FLOAT          Log interval in seconds (default: 5.0)
  --mode TEXT               Simulation mode: normal|flooding|poisoning|mixed (default: normal)
  --attack-nodes TEXT       Nodes to attack in mixed/attack modes (default: node_a)
  --attack-delay INT        Seconds before attack begins (default: 60)
  --duration INT            Total run duration in seconds, 0 = infinite (default: 0)
  --preserve-logs           Keep existing logs instead of clearing them (default: clears logs)
  -h, --help                Show help message
```

## Log Clearing Behavior

⚠️ **Important**: By default, when you start a new simulation, the NDN_LOGS folder is **completely cleared** to prevent mixing data from different runs.

**Clear logs (default behavior):**
```bash
python generator.py
# Clears NDN_LOGS/, then starts fresh logging
```

**Preserve existing logs (append mode):**
```bash
python generator.py --preserve-logs
# Appends to existing metrics.jsonl files without clearing
```

Use `--preserve-logs` when you want to:
- Combine multiple simulation runs into one log file
- Resume logging after stopping the simulator
- Accumulate data from sequential tests

## Example Workflows

### Scenario 1: Monitor Attack Detection (10 minutes)
Start with normal operation, then enable attack detection at 60 seconds:
```bash
python generator.py --mode flooding --attack-nodes node_a --duration 600
```

### Scenario 2: Multi-Node Attack (15 minutes)
Multiple nodes under simultaneous attacks:
```bash
python generator.py --mode mixed --attack-nodes node_a,node_b --duration 900 --attack-delay 30
```

### Scenario 3: High-Frequency Logging (1 second intervals)
```bash
python generator.py --interval 1.0 --duration 300
```

### Scenario 4: Single Node Testing
```bash
python generator.py --nodes test_node --output-dir ./test_logs
```

## Output Format

Each `metrics.jsonl` file contains one JSON object per line:

```json
{
  "timestamp": "2026-03-08T06:20:03.063749",
  "node": "node_a",
  "nPitEntries": 3,
  "nInInterests": 207,
  "nOutInterests": 204,
  "nInData": 185,
  "nInNacks": 2,
  "nOutNacks": 4,
  "nSatisfiedInterests": 179,
  "nUnsatisfiedInterests": 4,
  "nCsEntries": 170,
  "nHits": 0,
  "nMisses": 212
}
```

### Fields Description
- `timestamp`: ISO 8601 format timestamp (e.g., `2026-03-08T06:20:03.063749`)
- `node`: Node name identifier
- `nPitEntries`: Number of entries in the Pending Interest Table
- `nInInterests`: Total incoming interests (cumulative)
- `nOutInterests`: Total outgoing interests (cumulative)
- `nInData`: Total incoming data packets (cumulative)
- `nInNacks`: Total incoming NACKs (cumulative)
- `nOutNacks`: Total outgoing NACKs (cumulative)
- `nSatisfiedInterests`: Total satisfied interests (cumulative)
- `nUnsatisfiedInterests`: Total unsatisfied interests (cumulative)
- `nCsEntries`: Number of entries in Content Store (cache)
- `nHits`: Cache hit count (cumulative)
- `nMisses`: Cache miss count (cumulative)

## Folder Structure

```
NDN_LOGS/
├── node_a/
│   └── metrics.jsonl
├── node_b/
│   └── metrics.jsonl
├── node_c/
│   └── metrics.jsonl
├── node_d/
│   └── metrics.jsonl
└── node_e/
    └── metrics.jsonl
```

**Behavior:**
- Directories are created automatically on startup
- **By default: Logs folder is cleared** when simulation starts (prevents accidental data mixing)
- **With `--preserve-logs`: Existing files are appended** to without clearing
- Use absolute or relative paths with `--output-dir`

## Live Status Display

While running, the simulator displays a live status table showing:
- **Node**: Node name
- **Uptime**: Seconds since startup (internal tracking, not in logs)
- **Status**: NORMAL or ATTACKING
- **In-Interests/s**: Interest rate for current tick
- **Satisfaction %**: Percentage of satisfied interests

## Graceful Shutdown

Press `Ctrl+C` to gracefully shutdown. The simulator will:
1. Stop accepting new write operations
2. Flush all pending writes
3. Exit cleanly

## Features

✅ Multi-threaded node simulation  
✅ Realistic metric generation with state tracking  
✅ Three attack modes + mixed mode  
✅ Live status dashboard (with optional Rich library for colors)  
✅ Configurable logging intervals and duration  
✅ Automatic directory creation  
✅ JSONL append mode (non-destructive)  
✅ Graceful shutdown handling  
✅ Deterministic node variety (different base rates per node)  

## Requirements

- Python 3.7+
- Optional: `rich` (for colored status table)

## Notes

- Each node has slightly different base rates to prevent identical behavior
- Counters are monotonically increasing (realistic for NDN)
- Attack modes kick in after configurable delay (default 60s)
- Satisfaction ratio is correctly calculated based on satisfied/unsatisfied interests
- Console output gracefully degrades without `rich` library

## Troubleshooting

**Missing `rich` library?**
The simulator works fine without it—the status display will use basic text output instead.

**Logs not appearing?**
- Check that the output directory is writable
- Verify no permission issues in the NDN_LOGS folder
- Check console for error messages

**Need to analyze logs?**
Use standard text tools:
```bash
# Count lines (events) in a node's log
wc -l NDN_LOGS/node_a/metrics.jsonl

# Pretty-print last entry
tail -1 NDN_LOGS/node_a/metrics.jsonl | python -m json.tool

# Filter entries by node name
jq 'select(.node == "node_a")' NDN_LOGS/node_a/metrics.jsonl

# Filter entries with high interest rate
jq 'select(.nInInterests > 200)' NDN_LOGS/node_a/metrics.jsonl
```
