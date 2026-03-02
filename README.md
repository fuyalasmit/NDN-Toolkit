# NDN Network Monitoring & Simulation Suite

A comprehensive toolkit for simulating, monitoring, and analyzing Named Data Networking (NDN) networks. This suite enables you to generate realistic NDN node metrics, simulate network attacks, and monitor network health in real-time through an interactive web dashboard.

## Overview

This project consists of three main components:

1. **Logs_Generator** - Simulates NDN nodes and generates realistic metrics logs
2. **Monitor** - Real-time web dashboard for monitoring NDN network metrics
3. **MiniNDN_Scripts** - Production scripts for collecting metrics from actual MiniNDN simulations

## Quick Start Guide

### Basic Workflow

The typical workflow involves two steps:

1. **Generate logs** using Logs_Generator (in one terminal)
2. **Monitor logs** using Monitor web dashboard (in another terminal)

#### Step 1: Generate NDN Logs

Open a terminal and navigate to the Logs_Generator directory:

```bash
cd Logs_Generator

# Install dependencies
pip install -r requirements.txt

# Start generating logs (runs indefinitely)
python generator.py

# The logs will be generated in: Logs_Generator/NDN_LOGS/
```

This will start 5 simulated nodes (node_a through node_e) generating metrics every 5 seconds.

#### Step 2: Monitor the Logs

Open a **second terminal** and navigate to the Monitor directory:

```bash
cd Monitor

# Install dependencies
pip install -r requirements.txt

# Start the monitoring dashboard, pointing to the Logs_Generator output
python monitor.py --logs-dir ../Logs_Generator/NDN_LOGS

# Open your browser to: http://localhost:8000
```

The web dashboard will now display real-time metrics from your simulated nodes!
