#!/usr/bin/env python3
"""
NDN Node Logging Simulator
Generates realistic NDN metrics logs with support for attack simulations
"""

import argparse
import json
import os
import random
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from typing import Dict, List, Optional
import sys


class NDNNode:
    """Simulates a single NDN node and manages its metrics."""
    
    def __init__(self, name: str, mode: str = "normal", under_attack: bool = False, attack_delay: int = 60):
        self.name = name
        self.mode = mode  # normal, flooding, poisoning, mixed
        self.under_attack = under_attack
        self.attack_delay = attack_delay
        self.attack_active = False
        
        # Calculate node-specific random offsets for variety
        self.base_interest_rate = random.uniform(0.8, 1.5)  # interests per tick
        self.base_cache_growth = random.uniform(2, 5)  # cache entries per tick
        
        # Start time is when the node "boots"
        self.start_time = datetime.now()
        self.start_time_str = self.start_time.strftime("%Y%m%dT%H%M%S.%f")
        self.first_read = True
        
        # Counters (monotonically increasing)
        self.n_in_interests = random.randint(0, 50)
        self.n_out_interests = self.n_in_interests - random.randint(0, 5)
        self.n_in_data = random.randint(0, 40)
        self.n_out_data = random.randint(0, 40)
        self.n_in_nacks = 0
        self.n_out_nacks = 0
        self.n_satisfied_interests = random.randint(0, 35)
        self.n_unsatisfied_interests = 0
        
        # Cache metrics
        self.n_hits = 0
        self.n_misses = random.randint(0, 50)
        
        # Growing counters (stabilize or grow slowly)
        self.n_name_tree_entries = random.randint(40, 80)
        self.n_fib_entries = random.randint(10, 20)
        self.n_pit_entries = random.randint(1, 8)
        self.n_measurements_entries = random.randint(0, 3)
        self.n_cs_entries = random.randint(50, 150)
        
        # Last rates for status display
        self.last_in_interests_rate = 0.0
        
    def get_current_time_str(self) -> str:
        """Get current time in ISO format."""
        now = datetime.now()
        return now.strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    def get_uptime(self) -> int:
        """Get uptime in seconds."""
        return int((datetime.now() - self.start_time).total_seconds())
    
    def get_satisfaction_ratio(self) -> float:
        """Calculate satisfaction ratio."""
        total = self.n_satisfied_interests + self.n_unsatisfied_interests
        if total == 0:
            return 0.95
        return self.n_satisfied_interests / total
    
    def update_metrics(self):
        """Update metrics for this tick."""
        uptime = self.get_uptime()
        
        # Check if attack should activate
        if self.under_attack and not self.attack_active and uptime >= self.attack_delay:
            self.attack_active = True
        
        if self.attack_active:
            self._update_attack_metrics(uptime)
        else:
            self._update_normal_metrics(uptime)
    
    def _update_normal_metrics(self, uptime: int):
        """Update metrics under normal conditions."""
        # Interest counters grow slowly and steadily
        interest_delta = int(self.base_interest_rate + random.uniform(-0.3, 0.5))
        interest_delta = max(0, interest_delta)
        self.n_in_interests += interest_delta
        self.last_in_interests_rate = interest_delta
        
        # Out interests is slightly less
        out_delta = max(0, interest_delta - random.randint(0, 2))
        self.n_out_interests += out_delta
        
        # Data responses grow (with ~95% satisfaction)
        data_delta = int(out_delta * 0.85) + random.randint(0, 1)
        self.n_in_data += data_delta
        self.n_out_data += data_delta
        
        # Nacks are rare
        if random.random() < 0.05:
            self.n_in_nacks += random.randint(0, 1)
        if random.random() < 0.08:
            self.n_out_nacks += random.randint(0, 1)
        
        # Satisfied interests
        satisfied_delta = int(data_delta * 0.95) + random.randint(0, 1)
        self.n_satisfied_interests += satisfied_delta
        
        # Unsatisfied interests
        unsatisfied_delta = max(0, interest_delta - satisfied_delta)
        self.n_unsatisfied_interests += unsatisfied_delta
        
        # Name tree grows slowly
        if uptime % 20 < 5 and random.random() < 0.3:
            self.n_name_tree_entries = min(120, self.n_name_tree_entries + 1)
        
        # FIB is relatively stable
        if self.n_fib_entries < 15 and random.random() < 0.1:
            self.n_fib_entries += 1
        
        # PIT fluctuates based on interest rate
        delta_pit = random.randint(0, 3) - 1
        self.n_pit_entries = max(1, min(10, self.n_pit_entries + delta_pit))
        
        # Measurements
        if random.random() < 0.15:
            self.n_measurements_entries = min(5, self.n_measurements_entries + 1)
        
        # Cache grows over time
        cache_delta = int(self.base_cache_growth + random.uniform(-1, 1))
        cache_delta = max(0, cache_delta)
        self.n_cs_entries = min(300, self.n_cs_entries + cache_delta)
        
        # Cache hits and misses
        if random.random() < 0.02:  # Occasional cache hit
            self.n_hits += random.randint(0, 1)
        self.n_misses += interest_delta  # Misses grow with interests
    
    def _update_attack_metrics(self, uptime: int):
        """Update metrics under attack conditions."""
        if self.mode == "flooding" or (self.mode == "mixed" and self.under_attack):
            # Interest flooding attack
            # Massive spike in inInterests
            interest_delta = random.randint(50, 120)
            self.n_in_interests += interest_delta
            self.last_in_interests_rate = interest_delta
            
            # Out interests slightly less due to rate limiting
            out_delta = int(interest_delta * random.uniform(0.7, 0.9))
            self.n_out_interests += out_delta
            
            # Low satisfaction - only 20-40% satisfied
            satisfied_delta = int(out_delta * random.uniform(0.15, 0.35))
            self.n_satisfied_interests += satisfied_delta
            unsatisfied_delta = out_delta - satisfied_delta
            self.n_unsatisfied_interests += unsatisfied_delta
            
            # Data and nacks remain low
            self.n_in_data += random.randint(0, 5)
            self.n_out_data += random.randint(0, 5)
            self.n_in_nacks += random.randint(1, 3)
            self.n_out_nacks += random.randint(1, 4)
            
            # PIT grows significantly
            self.n_pit_entries = min(10, self.n_pit_entries + random.randint(1, 4))
            
            # Cache misses increase dramatically during attack
            self.n_misses += interest_delta
            
        elif self.mode == "poisoning" or (self.mode == "mixed" and self.under_attack):
            # Cache poisoning attack
            # Cache grows abnormally fast
            cache_delta = random.randint(15, 40)
            self.n_cs_entries += cache_delta
            self.last_in_interests_rate = random.uniform(1, 3)
            
            # Low satisfaction
            interest_delta = random.randint(1, 5)
            self.n_in_interests += interest_delta
            self.n_out_interests += interest_delta - random.randint(0, 1)
            
            satisfied_delta = max(0, interest_delta - random.randint(2, 4))
            self.n_satisfied_interests += satisfied_delta
            self.n_unsatisfied_interests += interest_delta - satisfied_delta
            
            self.n_in_data += random.randint(0, 2)
            self.n_out_data += random.randint(0, 2)
            
            # Cache metrics during poisoning
            self.n_misses += random.randint(0, 3)
    
    def generate_log_entry(self) -> Dict:
        """Generate a complete log entry in the new format."""
        return {
            "timestamp": self.get_current_time_str(),
            "node": self.name,
            "nPitEntries": self.n_pit_entries,
            "nInInterests": self.n_in_interests,
            "nOutInterests": self.n_out_interests,
            "nInData": self.n_in_data,
            "nInNacks": self.n_in_nacks,
            "nOutNacks": self.n_out_nacks,
            "nSatisfiedInterests": self.n_satisfied_interests,
            "nUnsatisfiedInterests": self.n_unsatisfied_interests,
            "nCsEntries": self.n_cs_entries,
            "nHits": self.n_hits,
            "nMisses": self.n_misses,
        }


class NDNSimulator:
    """Main simulator managing multiple nodes and logging."""
    
    def __init__(
        self,
        output_dir: str,
        nodes: List[str],
        interval: float,
        mode: str,
        attack_nodes: List[str],
        attack_delay: int,
        duration: int,
        preserve_logs: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.nodes_to_run = nodes
        self.interval = interval
        self.mode = mode
        self.attack_nodes = set(attack_nodes)
        self.attack_delay = attack_delay
        self.duration = duration
        self.start_time = time.time()
        
        # Clear existing logs unless preserve_logs is set
        if not preserve_logs:
            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
        
        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for node_name in self.nodes_to_run:
            node_dir = self.output_dir / node_name
            node_dir.mkdir(parents=True, exist_ok=True)
        
        # Create node objects
        self.nodes: Dict[str, NDNNode] = {}
        for node_name in self.nodes_to_run:
            is_attacked = node_name in self.attack_nodes
            self.nodes[node_name] = NDNNode(
                name=node_name,
                mode=mode if is_attacked else "normal",
                under_attack=is_attacked,
                attack_delay=attack_delay,
            )
        
        # Threading
        self.threads: Dict[str, Thread] = {}
        self.stop_event = Event()
        self.lock = Lock()
        self.stats_lock = Lock()
        
    def log_metrics(self, node_name: str, entry: Dict):
        """Write a metric entry to the node's JSONL file."""
        node_dir = self.output_dir / node_name
        metrics_file = node_dir / "metrics.jsonl"
        
        with self.lock:
            with metrics_file.open("a") as f:
                f.write(json.dumps(entry) + "\n")
    
    def node_worker(self, node_name: str):
        """Worker thread for a single node."""
        node = self.nodes[node_name]
        
        while not self.stop_event.is_set():
            try:
                node.update_metrics()
                entry = node.generate_log_entry()
                self.log_metrics(node_name, entry)
                
                time.sleep(self.interval)
                
                # Check duration
                if self.duration > 0:
                    elapsed = time.time() - self.start_time
                    if elapsed >= self.duration:
                        self.stop_event.set()
                        break
                        
            except Exception as e:
                print(f"Error in {node_name}: {e}", file=sys.stderr)
                break
    
    def display_status(self):
        """Display live status table."""
        try:
            from rich.console import Console
            from rich.table import Table
            console = Console()
        except ImportError:
            console = None
        
        while not self.stop_event.is_set():
            try:
                if console:
                    table = Table(title="NDN Node Status")
                    table.add_column("Node", style="cyan")
                    table.add_column("Uptime (s)", style="green")
                    table.add_column("Status", style="yellow")
                    table.add_column("In-Interests/s", style="magenta")
                    table.add_column("Satisfaction %", style="blue")
                    
                    for node_name in self.nodes_to_run:
                        node = self.nodes[node_name]
                        uptime = node.get_uptime()
                        status = "ATTACKING" if node.attack_active else "NORMAL"
                        status_style = "red" if node.attack_active else "green"
                        sat_ratio = node.get_satisfaction_ratio() * 100
                        
                        table.add_row(
                            node_name,
                            str(uptime),
                            f"[{status_style}]{status}[/{status_style}]",
                            f"{node.last_in_interests_rate:.1f}",
                            f"{sat_ratio:.1f}%"
                        )
                    
                    console.clear()
                    console.print(table)
                else:
                    # Fallback to simple print
                    print("\n" + "="*70)
                    print(f"{'Node':<15} {'Uptime':<10} {'Status':<12} {'In-Int/s':<12} {'Sat %':<10}")
                    print("-"*70)
                    for node_name in self.nodes_to_run:
                        node = self.nodes[node_name]
                        uptime = node.get_uptime()
                        status = "ATTACKING" if node.attack_active else "NORMAL"
                        sat_ratio = node.get_satisfaction_ratio() * 100
                        print(f"{node_name:<15} {uptime:<10} {status:<12} {node.last_in_interests_rate:<12.1f} {sat_ratio:<10.1f}%")
                
                time.sleep(2)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Display error: {e}", file=sys.stderr)
                break
    
    def run(self):
        """Start all node workers and status display."""
        print(f"Starting NDN simulator with {len(self.nodes)} nodes...")
        print(f"Mode: {self.mode}")
        if self.attack_nodes:
            print(f"Attack nodes: {', '.join(sorted(self.attack_nodes))}")
        print(f"Output directory: {self.output_dir}")
        print(f"Logging every {self.interval}s")
        if self.duration > 0:
            print(f"Duration: {self.duration}s")
        print("-" * 70)
        
        # Start node worker threads
        for node_name in self.nodes_to_run:
            thread = Thread(target=self.node_worker, args=(node_name,), daemon=False)
            thread.start()
            self.threads[node_name] = thread
        
        # Start status display
        status_thread = Thread(target=self.display_status, daemon=True)
        status_thread.start()
        
        # Wait for all workers
        try:
            for node_name, thread in self.threads.items():
                thread.join()
        except KeyboardInterrupt:
            print("\nShutting down gracefully...")
            self.stop_event.set()
            for thread in self.threads.values():
                thread.join(timeout=5)
        
        print("Simulation complete!")


def main():
    parser = argparse.ArgumentParser(
        description="NDN Node Logging Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Normal mode (clears logs by default)
  python generator.py
  
  # Interest flooding attack on node_a
  python generator.py --mode flooding --attack-nodes node_a
  
  # Cache poisoning with log preservation
  python generator.py --mode poisoning --attack-nodes node_a --preserve-logs
  
  # Mixed mode (append to existing logs)
  python generator.py --mode mixed --attack-nodes node_a --preserve-logs
        """
    )
    
    parser.add_argument(
        "--output-dir",
        default="./NDN_LOGS",
        help="Path to NDN_LOGS folder (default: ./NDN_LOGS)"
    )
    
    parser.add_argument(
        "--nodes",
        default="node_a,node_b,node_c,node_d,node_e",
        help="Comma-separated node names (default: node_a,node_b,node_c,node_d,node_e)"
    )
    
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Log interval in seconds (default: 5.0)"
    )
    
    parser.add_argument(
        "--mode",
        default="normal",
        choices=["normal", "flooding", "poisoning", "mixed"],
        help="Simulation mode (default: normal)"
    )
    
    parser.add_argument(
        "--attack-nodes",
        default="node_a",
        help="Comma-separated node names to attack in mixed/attack modes (default: node_a)"
    )
    
    parser.add_argument(
        "--attack-delay",
        type=int,
        default=60,
        help="Seconds before attack begins (default: 60)"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Total run duration in seconds, 0 = infinite (default: 0)"
    )
    
    parser.add_argument(
        "--preserve-logs",
        action="store_true",
        help="Preserve existing logs instead of clearing them (default: clears logs)"
    )
    
    args = parser.parse_args()
    
    # Parse node lists
    nodes = [n.strip() for n in args.nodes.split(",")]
    attack_nodes = [n.strip() for n in args.attack_nodes.split(",")]
    
    # Create and run simulator
    simulator = NDNSimulator(
        output_dir=args.output_dir,
        nodes=nodes,
        interval=args.interval,
        mode=args.mode,
        attack_nodes=attack_nodes,
        attack_delay=args.attack_delay,
        duration=args.duration,
        preserve_logs=args.preserve_logs,
    )
    
    simulator.run()


if __name__ == "__main__":
    main()
