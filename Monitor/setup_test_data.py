#!/usr/bin/env python3
"""
Test setup script for NDN Network Monitor
Creates sample NDN_LOGS directory structure with test metrics data
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta

def create_test_data(logs_dir="./test_NDN_LOGS"):
    """Create sample NDN_LOGS directory with test metrics."""
    
    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)
    
    # Create 3 test nodes
    nodes = ["node_a", "node_b", "node_c"]
    
    for node_name in nodes:
        node_dir = logs_path / node_name
        node_dir.mkdir(exist_ok=True)
        
        metrics_file = node_dir / "metrics.jsonl"
        
        # Generate sample metrics
        start_time = datetime(2026, 1, 31, 9, 9, 55, 267000)
        base_interests = 100
        base_data = 50
        base_satisfied = 95
        
        with open(metrics_file, 'w') as f:
            for i in range(20):
                current_time = start_time + timedelta(seconds=5*i)
                
                # Gradually increase values with some variation
                n_in_interests = base_interests + (i * 5) + (i % 3)
                n_out_interests = base_interests + (i * 4) + (i % 2)
                n_in_data = base_data + i
                n_satisfied = base_satisfied + min(i, 3) - (i % 5)
                
                entry = {
                    "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    "node": node_name,
                    "nPitEntries": 3 + i // 5,
                    "nInInterests": n_in_interests,
                    "nOutInterests": n_out_interests,
                    "nInData": n_in_data,
                    "nInNacks": 1 + (i % 4),
                    "nOutNacks": 4 + (i % 2),
                    "nSatisfiedInterests": n_satisfied,
                    "nUnsatisfiedInterests": 10 + (i % 3) - min(2, i),
                    "nCsEntries": 114 + (i * 2),
                    "nHits": i % 3,
                    "nMisses": n_in_interests - (i % 3)
                }
                
                f.write(json.dumps(entry) + '\n')
        
        print(f"✓ Created {metrics_file} with 20 sample entries")
    
    print(f"\n✓ Test data created in: {logs_path.absolute()}")
    print(f"\nTo run the monitor with test data:")
    print(f"  python monitor.py --logs-dir {logs_dir} --port 8000")
    print(f"\nThen open: http://localhost:8000")

if __name__ == "__main__":
    create_test_data()
