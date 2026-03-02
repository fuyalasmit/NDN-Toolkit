# NDN Network Monitor - Quick Start Guide

## 🚀 Get Started in 3 Commands

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate test data (optional, for quick demo)
python setup_test_data.py && python monitor.py --logs-dir ./test_NDN_LOGS

# 3. Open browser
# http://localhost:8000
```

## 📋 Project Overview

This is a professional NDN (Named Data Networking) real-time monitoring dashboard.

### What It Does
- **Watches** NDN_LOGS directory for new nodes and metrics
- **Tails** metrics.jsonl files in real-time (~5 second updates)
- **Computes** derived metrics (interest rate, satisfaction ratio, NACK rate, etc.)
- **Detects** anomalies (Interest Flooding, Cache Poisoning)
- **Displays** everything in a beautiful, interactive web dashboard
- **Alerts** when problems detected with configurable thresholds

### Tech Stack
- **Backend**: Python FastAPI + WebSocket + async file watching
- **Frontend**: Single HTML file (Tailwind CSS + Chart.js CDN + vanilla JS)
- **No dependencies**: No database, all data in memory (last 100 entries per node)

## 🎯 Key Features

✅ **Real-time Updates** - WebSocket pushes updates every 5 seconds  
✅ **Auto-discovery** - Finds nodes as folders appear  
✅ **Anomaly Detection** - Interest Flooding + Cache Poisoning detection  
✅ **Beautiful Dashboard** - Dark theme, charts, alerts, metrics tables  
✅ **Configurable Thresholds** - Change alert levels in settings  
✅ **No Build Step** - Single HTML file, runs instantly  
✅ **Professional Design** - Monitoring-grade interface with animations  

## 📊 Dashboard Components

- **Header**: Status indicator, alert bell, settings
- **Node Selector**: Choose "All" or specific nodes
- **Metrics Cards**: Interest Rate, Satisfaction Ratio, PIT Size, CS Entries
- **Time Series Charts**: 4 charts showing last 20 data points
- **Alert Panel**: CRITICAL/WARNING alerts with ACK buttons
- **Metrics Table**: Latest values per node with color-coding
- **Settings Modal**: Configure anomaly detection thresholds

## ⚠️ Anomaly Types

### 1. Interest Flooding Attack
- **Detects**: Unusually high interest packet rate
- **Default Warning**: > 50 int/sec
- **Default Critical**: > 100 int/sec

### 2. Cache Poisoning / High Drop Rate
- **Detects**: Low satisfaction ratio
- **Default Warning**: < 75% satisfaction
- **Default Critical**: < 50% satisfaction

## 🔧 Configuration

Edit thresholds via:
1. **Web UI**: Click ⚙️ button → Settings modal
2. **API**: POST /api/config with new thresholds
3. **Code**: Modify AnomalyThresholds in monitor.py

## 📁 Input Format

Create `NDN_LOGS/{node_name}/metrics.jsonl` with JSON lines:

```json
{"startTime":"20260131T090955.267000","currentTime":"20260131T091543.778000","uptime":348,"nNameTreeEntries":60,"nFibEntries":17,"nPitEntries":3,"nMeasurementsEntries":0,"nCsEntries":114,"nInInterests":228,"nOutInterests":219,"nInData":160,"nOutData":179,"nInNacks":1,"nOutNacks":4,"nSatisfiedInterests":158,"nUnsatisfiedInterests":7}
```

## 🌐 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/nodes | List all nodes |
| GET | /api/nodes/{node}/history | Get node metrics history |
| GET | /api/alerts | Get alerts |
| POST | /api/alerts/{id}/acknowledge | Mark alert as read |
| GET | /api/config | Get thresholds |
| POST | /api/config | Update thresholds |
| WS | /ws | Real-time updates |

## 🐛 Troubleshooting

**No nodes showing?**
- Create NDN_LOGS directory: `mkdir -p NDN_LOGS/node_a`
- Add metrics.jsonl with data

**Charts empty?**
- Ensure metrics.jsonl has valid JSON lines
- Check browser console for errors

**WebSocket disconnects?**
- Normal, auto-reconnects every 3 seconds
- Check `python monitor.py` output for errors

**Alerts not firing?**
- Verify interest_rate is being computed (needs 2+ entries)
- Check threshold values in Settings
- Monitor requires time_delta > 0 to compute rates

## 📈 Performance

- **Memory**: 100 entries × N nodes kept in memory
- **CPU**: Minimal - polling every 2 seconds, WebSocket every 5
- **Network**: WebSocket messages ~2KB per update
- **Can handle**: 10+ nodes easily, 100+ with tuning

## 🎓 Learning Points

This is an excellent example of:
- Real-time monitoring with WebSockets
- Anomaly detection algorithms
- FastAPI async patterns
- Chart.js for time series
- Dark theme UI design
- File system watching
- Network protocol monitoring

## 📝 Next Steps

1. Read [README.md](README.md) for complete documentation
2. Run `python setup_test_data.py` for demo data
3. Start with `python monitor.py --logs-dir ./test_NDN_LOGS`
4. Customize thresholds for your network
5. Integrate with your NDN simulation/testbed

## 📞 Support

- Check README.md troubleshooting section
- Run `python monitor.py --help` for options
- Review monitor.py source code (well-commented)
- Check browser DevTools console

---

**Ready to monitor your NDN network!** 🚀
