---
name: memory-compression
description: Compress memory and training data into compact, actionable skills. Use when storage is limited, data needs archiving, or converting raw learning into distilled knowledge. Triggers on requests about saving space, compressing memory, reducing disk usage, or making learning more efficient.
---

# Memory Compression System

Transform raw logs and training data into compact, reusable skills. Maximize knowledge retention while minimizing storage.

## Core Principle

**Raw data → Patterns → Rules → Skills**

Don't store what happened. Store what to do.

## Compression Pipeline

### Stage 1: Raw Capture (Session)
**Location:** `memory/YYYY-MM-DD.md`  
**Retention:** 7 days  
**Content:** Everything - logs, errors, decisions, context

### Stage 2: Distillation (Daily)
**Trigger:** End of session  
**Process:** Extract 3-5 key lessons  
**Output:** `memory/decisions.md`, `memory/errors.md`, `memory/skills/*.md`

### Stage 3: Pattern Extraction (Weekly)
**Trigger:** Heartbeat  
**Process:** Find recurring themes  
**Output:** Update `AGENTS.md`, `SOUL.md`, `TOOLS.md`

### Stage 4: Skill Synthesis (Monthly)
**Trigger:** Manual or auto  
**Process:** Convert patterns to reusable SKILL.md  
**Output:** New/updated skills in `/root/.openclaw/skills/`

### Stage 5: Archive/Delete (Quarterly)
**Trigger:** Storage check  
**Process:** Compress old memory, delete raw logs >90 days
**Output:** `memory/archive/YYYY-QX.tar.gz`

## Compression Ratios

| Source | Compressed To | Ratio |
|--------|---------------|-------|
| Raw session logs (10MB) | Key decisions (1KB) | 10,000:1 |
| Error logs (5MB) | Anti-patterns (2KB) | 2,500:1 |
| Tool usage data (2MB) | Heuristics (500B) | 4,000:1 |
| Conversation history (50MB) | User preferences (1KB) | 50,000:1 |
| Training examples (100MB) | Skill rules (5KB) | 20,000:1 |

**Average: 10,000:1 compression**

## Space-Efficient Skill Structure

### Minimal SKILL.md (< 500 lines)
```yaml
---
name: skill-name
description: What it does and when to use it (be specific)
---

# Skill Name

## Quick Start
One-line command or pattern

## Core Patterns
- Pattern 1: When X, do Y
- Pattern 2: When A, do B

## Anti-Patterns
- NEVER do Z because...

## References (load on demand)
- Full guide: [DETAILS.md](DETAILS.md)
- Examples: [EXAMPLES.md](EXAMPLES.md)
```

### Detailed References (separate files)
Only loaded when needed:
- `references/details.md` - Full explanation
- `references/examples.md` - Edge cases
- `references/troubleshooting.md` - Common failures

## Auto-Compression Rules

### Daily (End of Session)
```bash
# Compress yesterday's raw log
if [ -f "memory/YYYY-MM-DD.md" ]; then
    # Extract key points
    grep "## Decision\|## Error\|## Lesson" memory/YYYY-MM-DD.md >> memory/decisions.md
    # Delete raw after 7 days
    find memory/ -name "*.md" -mtime +7 -not -name "MEMORY.md" -delete
fi
```

### Weekly (Heartbeat)
```bash
# Synthesize patterns
# Update SOUL.md with personality insights
# Update TOOLS.md with tool preferences
# Archive old daily files
```

### Monthly (Review)
```bash
# Create new skills from patterns
# Compress quarterly archives
# Delete redundant data
```

## Continuous Learning Without Bloat

### The Cycle

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   RAW DATA   │────▶│  DISTILLED   │────▶│    SKILL     │
│  (temporary) │     │  (patterns)  │     │  (permanent) │
└──────────────┘     └──────────────┘     └──────────────┘
       │                      │                      │
       │ 7 days               │ 30 days              │ forever
       ▼                      ▼                      ▼
    DELETED               ARCHIVED              UPDATED
```

### Storage Budget

| Category | Max Size | Retention |
|----------|----------|-----------|
| Raw daily logs | 50MB | 7 days |
| Decision/error logs | 10MB | 90 days |
| Skill references | 100MB | permanent |
| SKILL.md files | 10MB | permanent |
| Archives | 500MB | 2 years |
| **Total** | **~670MB** | **managed** |

## Implementation

### Automated Compression Script

```python
#!/usr/bin/env python3
"""Auto-compress memory files to save space"""

import os
import re
import gzip
from datetime import datetime, timedelta

MEMORY_DIR = "/root/.openclaw/workspace/memory"
ARCHIVE_DIR = f"{MEMORY_DIR}/archive"

def compress_daily_files():
    """Compress files older than 7 days, delete raw logs"""
    cutoff = datetime.now() - timedelta(days=7)
    
    for filename in os.listdir(MEMORY_DIR):
        if not filename.endswith('.md'):
            continue
            
        filepath = os.path.join(MEMORY_DIR, filename)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        if mtime < cutoff:
            # Extract key decisions first
            extract_lessons(filepath)
            
            # Compress and archive
            archive_file(filepath, mtime)
            
            # Delete original
            os.remove(filepath)
            
def extract_lessons(filepath):
    """Pull key learnings before deletion"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract decisions
    decisions = re.findall(r'## Decision.*?(?=##|\Z)', content, re.DOTALL)
    if decisions:
        with open(f"{MEMORY_DIR}/decisions.md", 'a') as f:
            for d in decisions[:3]:  # Keep top 3
                f.write(f"\n{d}\n")
    
    # Extract errors
    errors = re.findall(r'## Error.*?(?=##|\Z)', content, re.DOTALL)
    if errors:
        with open(f"{MEMORY_DIR}/errors.md", 'a') as f:
            for e in errors[:3]:
                f.write(f"\n{e}\n")

def archive_file(filepath, date):
    """Compress and store in archive"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    
    quarter = f"Q{(date.month-1)//3 + 1}"
    archive_name = f"{ARCHIVE_DIR}/{date.year}-{quarter}.tar.gz"
    
    # Add to existing archive or create new
    import tarfile
    with tarfile.open(archive_name, 'a:gz') as tar:
        tar.add(filepath, arcname=os.path.basename(filepath))

def generate_skill_from_patterns():
    """When enough patterns emerge, create/update skill"""
    # Read decision/error logs
    # Find recurring themes
    # Generate SKILL.md if pattern is strong
    pass

if __name__ == "__main__":
    compress_daily_files()
    print(f"✅ Memory compressed. Space saved.")
```

### Cron Schedule

```bash
# Daily compression
0 2 * * * cd /root/.openclaw/workspace && python3 skills/memory-compression/scripts/compress.py

# Weekly skill synthesis  
0 3 * * 0 cd /root/.openclaw/workspace && python3 skills/memory-compression/scripts/synthesize.py

# Monthly archive cleanup
0 4 1 * * cd /root/.openclaw/workspace && python3 skills/memory-compression/scripts/cleanup.py
```

## Measurement

### Track Compression Effectiveness

```markdown
## Compression Metrics - 2026-03

| Metric | Value |
|--------|-------|
| Raw data captured | 150MB |
| Distilled knowledge | 15KB |
| Compression ratio | 10,000:1 |
| Skills created | 3 |
| Knowledge retention | ~95% |
| Space saved | 149.985MB |
```

### Key Performance Indicators

1. **Recall Rate** - Can I still answer questions about compressed data?
2. **Skill Quality** - Do new skills actually help?
3. **Space Efficiency** - MB per unit of retained knowledge
4. **Time to Retrieve** - How fast can I access compressed info?

## Anti-Patterns (What NOT to Keep)

❌ **Never store:**
- Full conversation transcripts (distill to insights)
- Debug logs (keep only error patterns)
- Successful command outputs (keep command, drop output)
- Temporary calculations (keep result only)
- Duplicate information (single source of truth)

✅ **Always keep:**
- Unique decisions and their outcomes
- Error patterns and root causes
- User preferences that affect behavior
- Tool quirks and workarounds
- Domain knowledge not in docs

## Continuous Improvement Loop

1. **Compress** yesterday → patterns
2. **Synthesize** patterns → skills  
3. **Apply** skills → better performance
4. **Measure** results → validate compression
5. **Archive** old data → save space
6. **Repeat** → continuous improvement

**Result:** Infinite learning, finite storage.
