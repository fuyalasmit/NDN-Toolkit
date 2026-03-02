## Overview

This folder contains scripts for MiniNDN simulations and metrics collection.

## Files

- **file_metrics_collector.py**: Production-ready MiniNDN script
    - Install at: `apps/custom/file_metrics_collector.py` in your MiniNDN directory
    
- **mnndn.py**: Sample script for MiniNDN environment
    - Streams metrics to the logs folder

## Usage

### For Testing

Use the `Logs_Generator` project instead to simulate production metrics without running a full simulation.

### For Production

Deploy `file_metrics_collector.py` in your MiniNDN environment to collect real simulation metrics.

## Status

These scripts are actively developed. Production features are still maturing.
