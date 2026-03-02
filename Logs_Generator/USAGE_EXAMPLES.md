# Complete Usage Examples for NDN Simulator

## Log Clearing Behavior (Important!)

**By default**, every simulation **clears the NDN_LOGS folder** to prevent mixing data from different runs.

```bash
# Clears logs, then starts fresh
python generator.py

# To append to existing logs instead
python generator.py --preserve-logs
```

## Quick Start

```bash
# Start with 5 default nodes in normal mode
python generator.py

# Start with custom nodes
python generator.py --nodes sensor_1,sensor_2,sensor_3
```

## Mode Examples

### 1. Normal Operation (Baseline)
```bash
# Run for 2 minutes with 5-second intervals
python generator.py --duration 120 --interval 5

# High-frequency logging (1 second intervals)
python generator.py --interval 1.0 --duration 180
```

### 2. Interest Flooding Attack Detection
```bash
# Single node under flooding attack
python generator.py --mode flooding --attack-nodes node_a --duration 120

# Multiple nodes flooding (simulating coordinated DDoS)
python generator.py --mode flooding --attack-nodes node_a,node_b,node_c --duration 120

# Delayed attack start (attack begins after 30 seconds)
python generator.py --mode flooding --attack-nodes node_a --attack-delay 30 --duration 180
```

### 3. Cache Poisoning Attack Detection
```bash
# Single node cache poisoning
python generator.py --mode poisoning --attack-nodes node_b --duration 120

# Multiple nodes poisoned
python generator.py --mode poisoning --attack-nodes node_a,node_b --duration 120
```

### 4. Mixed Mode (Best for Monitor Testing)
```bash
# One node flooding, others normal
python generator.py --mode mixed --attack-nodes node_a --duration 180

# One node poisoned, others normal  
python generator.py --mode mixed --attack-nodes node_b --duration 180

# Complex scenario: Multiple attacks on different nodes
python generator.py --mode mixed --attack-nodes node_a,node_c --duration 180

# Gradual ramp-up: Attack begins after 1 minute
python generator.py --mode mixed --attack-nodes node_a --attack-delay 60 --duration 300
```

## Real-World Scenarios

### Scenario: Monitor Validation (5 minutes total)
```bash
python generator.py --mode mixed --attack-nodes node_a \
  --attack-delay 30 --duration 300 --interval 2
```
Perfect for testing attack detection algorithms:
- First 30 seconds: Normal baseline
- Next 4:30: node_a attacking, others normal

### Scenario: Stress Test with High Volume
```bash
python generator.py --interval 0.5 --duration 600 --nodes test_1,test_2,test_3,test_4
```
Tests monitor throughput:
- 2 logs per second per node = 8 logs/sec total
- 10 minutes = 4,800 total entries

### Scenario: Multiple Simultaneous Attacks
```bash
python generator.py --mode mixed \
  --nodes data_1,data_2,data_3,data_4,data_5 \
  --attack-nodes data_1,data_3,data_5 \
  --attack-delay 20 \
  --duration 240
```
Complex scenario:
- 5 nodes, 3 under different attacks
- Staggered start (attacks begin at 20s)
- 4 minutes of data

### Scenario: Extended Baseline Collection
```bash
python generator.py --nodes prod_a,prod_b,prod_c,prod_d \
  --interval 10 --duration 3600
```
Establish normal operating profiles:
- 1 hour of data
- 10-second intervals (360 entries per node)

## Analysis Examples

### View Real-Time Logs
```bash
# Watch logs as they're written
tail -f NDN_LOGS/node_a/metrics.jsonl | jq

# Pretty-print last 10 entries
tail -10 NDN_LOGS/node_a/metrics.jsonl | jq
```

### Analyze Interest Rates
```bash
# Extract interest counts
jq '.nInInterests' NDN_LOGS/node_a/metrics.jsonl

# Find entries during attack window (uptime > 60)
jq 'select(.uptime > 60)' NDN_LOGS/node_a/metrics.jsonl | head -5 | jq

# Calculate average satisfaction ratio
jq '[.nSatisfiedInterests / (.nSatisfiedInterests + .nUnsatisfiedInterests)]' \
  NDN_LOGS/node_a/metrics.jsonl | jq 'add / length'
```

### Compare Node Behavior
```bash
# Create CSV for analysis
echo "Uptime,Node,InInt,Sat%" > analysis.csv
for node in node_a node_b node_c; do
  jq -r '[.uptime, "'$node'", .nInInterests, 
    (.nSatisfiedInterests/(.nSatisfiedInterests+.nUnsatisfiedInterests)*100)] | @csv' \
    NDN_LOGS/$node/metrics.jsonl >> analysis.csv
done
```

## Tips for Different Use Cases

| Use Case | Command | Duration |
|----------|---------|----------|
| Quick test | `python generator.py --duration 30` | 30s |
| Monitor validation | `python generator.py --mode mixed --attack-delay 30 --duration 300` | 5m |
| Performance test | `python generator.py --interval 0.5 --nodes n1,n2,n3,n4,n5 --duration 600` | 10m |
| Baseline collection | `python generator.py --interval 10 --duration 3600` | 1h |
| Stress test | `python generator.py --mode flooding --attack-delay 10 --duration 1800` | 30m |

## Node Behavior Reference

### Normal Mode
- Interest rate: 0.5–2 per second
- Satisfaction ratio: 90–96%
- Cache growth: 2–5 entries per tick
- NACKs: Rare (0–2 per tick)

### Flooding Attack Mode
- Interest rate: 50–120 per second
- Satisfaction ratio: 15–35%
- PIT entries spike dramatically
- Low data response rate

### Poisoning Attack Mode
- Cache growth: 15–40 entries per tick
- Satisfaction ratio: drops below 50%
- Cache hit ratio: <10%
- Interest rate remains moderate (1–5/sec)

## Cleanup Commands

```bash
# Clear logs directory manually (same as default behavior)
rm -rf NDN_LOGS/*

# Archive logs for later analysis
tar -czf ndn_logs_$(date +%Y%m%d_%H%M%S).tar.gz NDN_LOGS/

# Reset to empty state
rm -rf NDN_LOGS && mkdir -p NDN_LOGS/{node_a,node_b,node_c,node_d,node_e}
```

## Preserving Logs Across Runs

Use `--preserve-logs` to combine multiple simulations:

```bash
# Run 1: Baseline (logs are cleared by default)
python generator.py --nodes prod_a,prod_b --duration 60

# Run 2: Add attack data to same files (append mode)
python generator.py --nodes prod_a,prod_b --mode flooding --preserve-logs --duration 60

# Result: NDN_LOGS/prod_a/metrics.jsonl has 120 entries (60 + 60)
```

Useful for:
- Sequential attack simulations building on baseline
- Multi-phase testing scenarios
- Accumulating representative data sets
- Comparing before/after metrics
```

## Notes

1. The status table updates every 2 seconds
2. Each node operates independently in its own thread
3. Logs are appended to existing files (non-destructive)
4. Graceful shutdown on Ctrl+C preserves all data
5. Satisfaction ratio = satisfied / (satisfied + unsatisfied) interests
6. Cache hit ratio is implicit (cache_entries / total_interests)
