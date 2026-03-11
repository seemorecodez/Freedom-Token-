---
name: trading-health-monitor
description: Monitor trading bot health, detect errors, track trade execution, and alert on system issues. Use when user asks to monitor trading systems, check if bots are running, detect errors, or verify trades are executing.
---

# Trading System Health Monitor

Monitor kraken trading bots for:
- Process status (running/stopped)
- Error detection in logs
- Trade execution verification
- System health alerts

## Usage

### Quick Health Check
```bash
python3 /root/.openclaw/workspace/trading_health_monitor.py --once
```

### Continuous Monitoring
```bash
python3 /root/.openclaw/workspace/trading_health_monitor.py
```

### Check Specific Component
```bash
# Check if optimized scalper is running
pgrep -f kraken_optimized_scalper.py

# Check recent errors
tail -50 /root/.openclaw/workspace/optimized_scalper.log | grep -i error

# Check trade count
grep -c "⚡" /root/.openclaw/workspace/optimized_scalper.log
```

## Alerts

Alerts are written to `/root/.openclaw/workspace/trading_alerts.log` when:
- Processes stop unexpectedly
- Errors exceed threshold
- No trades executed for extended period

## Integration

Run as cron job for 24/7 monitoring:
```bash
openclaw cron add --name "trading-health" --schedule "every 5m" --command "python3 /root/.openclaw/workspace/trading_health_monitor.py --once"
```
