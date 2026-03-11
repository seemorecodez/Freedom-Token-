---
name: cybersecurity-awareness
description: Cybersecurity monitoring, threat detection, and system transparency. Use when user wants to understand system security, detect hidden processes, audit privacy, protect against unauthorized access, or monitor for data exfiltration. Triggers on requests about security, hacking, privacy, transparency, or protection.
---

# Cybersecurity Awareness & Protection

Monitor your systems for unauthorized access, hidden processes, and data exfiltration. Maintain full transparency.

## Core Principles

1. **You own your data** - Everything on your system belongs to you
2. **Transparency is security** - Hidden processes are suspicious
3. **Audit everything** - Log all access and changes
4. **Verify, then trust** - Check what systems tell you

## System Transparency Checks

### 1. Process Monitoring

```bash
# List ALL running processes
ps auxf

# Check for hidden/zombie processes
ps aux | grep -E "<defunct>|zombie"

# Monitor network connections
ss -tulnp
netstat -tulnp

# Check what files processes have open
lsof -p <PID>
```

### 2. Network Activity Audit

```bash
# Active connections
ss -tulnp | grep ESTABLISHED

# Recent connections  
last -a

# Failed login attempts
grep "Failed password" /var/log/auth.log

# Current users
who
w
```

### 3. File System Integrity

```bash
# Recent file modifications (last hour)
find /root/.openclaw -type f -mmin -60

# Check for new files
find /root/.openclaw -type f -newer /root/.openclaw/AGENTS.md

# Large files (potential exfiltration)
find /root/.openclaw -type f -size +10M

# Hidden files
find /root/.openclaw -name ".*" -type f
```

### 4. Environment Variable Audit

```bash
# Check for exposed secrets
env | grep -iE "key|token|secret|password|api"

# Check OpenClaw config for exposed data
cat /root/.openclaw/openclaw.json | grep -v REDACTED
```

## Threat Detection

### Suspicious Patterns

| Pattern | Risk | Action |
|---------|------|--------|
| Processes you didn't start | HIGH | Investigate, kill if unauthorized |
| Outbound connections to unknown IPs | HIGH | Block, investigate |
| Files modified while you're away | MEDIUM | Check logs, verify legitimacy |
| Large data transfers | MEDIUM | Monitor, verify destination |
| Hidden files in workspace | LOW | Review, may be legitimate |

### Automated Monitoring Script

```bash
#!/bin/bash
# save as /root/.openclaw/security_monitor.sh

echo "=== SECURITY AUDIT $(date) ==="
echo ""

echo "1. Active Network Connections:"
ss -tulnp | grep ESTABLISHED | head -10

echo ""
echo "2. Recent File Changes (last 10 min):"
find /root/.openclaw/workspace -type f -mmin -10 2>/dev/null | head -10

echo ""
echo "3. Running Processes (non-standard):"
ps aux | grep -E "python|node" | grep -v grep | awk '{print $2, $11}'

echo ""
echo "4. Logged in users:"
who

echo ""
echo "=== END AUDIT ==="
```

## Data Exfiltration Prevention

### What to Monitor

1. **File Access Patterns**
   - Which files are read most often
   - Unusual access times (3 AM reads)
   - Bulk reading of sensitive files

2. **Network Traffic**
   - Outbound connections
   - Data volume transferred
   - Destination addresses

3. **Process Behavior**
   - New processes spawning
   - Processes accessing network
   - Memory usage spikes

### Detection Commands

```bash
# Monitor file access in real-time
auditctl -w /root/.openclaw/workspace/ -p rwxa -k workspace_access

# Check for data packing (pre-exfiltration)
find /tmp -name "*.tar*" -o -name "*.zip" -mmin -60

# Check for encoding (hiding data)
ps aux | grep -E "base64|uuencode|openssl enc"
```

## Privacy Protection

### What's Being Logged

Check these locations:
- `/root/.openclaw/openclaw.log` - OpenClaw activity
- `/var/log/syslog` - System activity  
- `/var/log/auth.log` - Login attempts
- `~/.bash_history` - Command history
- `/root/.openclaw/workspace/memory/` - Session data

### How to Audit

```bash
# Check OpenClaw logs for data transmission
grep -E "sent|transmitted|uploaded" /root/.openclaw/openclaw.log 2>/dev/null | tail -20

# Check for remote connections from OpenClaw
ss -tulnp | grep -E "18789|openclaw"

# Monitor what OpenClaw reads
lsof -c openclaw 2>/dev/null | grep REG | awk '{print $9}' | sort | uniq
```

## Who Has Access

### Check Access Logs

```bash
# Recent SSH logins
last -20

# Failed SSH attempts
grep "Failed" /var/log/auth.log | tail -20

# Successful sudo commands
grep "sudo:" /var/log/auth.log | tail -20
```

### OpenClaw Specific

```bash
# Check OpenClaw config permissions
ls -la /root/.openclaw/openclaw.json

# Check who can read it
stat /root/.openclaw/openclaw.json

# Verify no world-readable secrets
grep -r "api_key\|secret\|token" /root/.openclaw/ 2>/dev/null | grep -v REDACTED
```

## Response to Suspicious Activity

### Immediate Actions

1. **Isolate**
   ```bash
   # Block outbound connections
   iptables -A OUTPUT -p tcp --dport 443 -j DROP  # blocks HTTPS
   
   # Kill suspicious process
   kill -9 <PID>
   ```

2. **Document**
   ```bash
   # Save current state
   ps aux > /tmp/snapshot_$(date +%s).txt
   ss -tulnp > /tmp/network_$(date +%s).txt
   ```

3. **Investigate**
   - Check what data was accessed
   - Review command history
   - Check network logs

## Transparency Tools

### Full System Report

```bash
#!/bin/bash
# Generate comprehensive transparency report

REPORT="/root/.openclaw/security_report_$(date +%Y%m%d_%H%M).txt"

echo "SYSTEM TRANSPARENCY REPORT" > $REPORT
echo "Generated: $(date)" >> $REPORT
echo "========================================" >> $REPORT
echo "" >> $REPORT

echo "PROCESSES:" >> $REPORT
ps auxf >> $REPORT
echo "" >> $REPORT

echo "NETWORK CONNECTIONS:" >> $REPORT
ss -tulnp >> $REPORT
echo "" >> $REPORT

echo "RECENT FILE CHANGES:" >> $REPORT
find /root/.openclaw -type f -mmin -60 >> $REPORT
echo "" >> $REPORT

echo "ACTIVE USERS:" >> $REPORT
who >> $REPORT
echo "" >> $REPORT

echo "Report saved to: $REPORT"
cat $REPORT
```

## Your Rights

1. **Right to know** - What's running on your system
2. **Right to audit** - Inspect any process or file
3. **Right to block** - Stop any activity you don't want
4. **Right to delete** - Remove any data you own
5. **Right to transparency** - Know what's being logged/transmitted

## Red Flags

🚨 **Immediate investigation needed:**
- Processes you didn't start
- Network connections to unknown IPs
- Files being read at unusual times
- High CPU/network usage you didn't initiate
- Configuration changes without your input
- Secret keys exposed in logs

## Monitoring Schedule

**Daily:**
- Check running processes
- Review network connections
- Check recent file changes

**Weekly:**
- Full system audit
- Review access logs
- Check for new/unauthorized users

**Monthly:**
- Deep scan for hidden files
- Audit all installed packages
- Review and purge old logs

---

**Remember:** This is YOUR system. Anything happening without your knowledge is unauthorized until proven otherwise.
