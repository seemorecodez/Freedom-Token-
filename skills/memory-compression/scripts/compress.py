#!/usr/bin/env python3
"""
Memory Compression Daemon
Compresses raw logs into compact skills and patterns
"""

import os
import re
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path

MEMORY_DIR = "/root/.openclaw/workspace/memory"
ARCHIVE_DIR = f"{MEMORY_DIR}/archive"
SKILLS_DIR = "/root/.openclaw/skills"

def setup_dirs():
    """Create necessary directories"""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(f"{MEMORY_DIR}/skills", exist_ok=True)

def extract_key_lessons(filepath):
    """Extract only the most valuable insights from a log file"""
    lessons = {
        'decisions': [],
        'errors': [],
        'patterns': [],
        'preferences': []
    }
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract decisions (with outcomes)
        decision_matches = re.findall(
            r'(?:## Decision|Decision:)\s*(.+?)(?=\n##|\n\n|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        for d in decision_matches[:2]:  # Keep only top 2
            lessons['decisions'].append(d.strip()[:500])  # Limit length
        
        # Extract errors (with fixes)
        error_matches = re.findall(
            r'(?:## Error|Error:|❌)\s*(.+?)(?=\n##|\n\n|\Z)',
            content,
            re.DOTAIL | re.IGNORECASE
        )
        for e in error_matches[:2]:
            lessons['errors'].append(e.strip()[:500])
        
        # Extract user preferences
        pref_patterns = [
            r'(?:user wants|user prefers|user said).*?(?=\n\n|\n##|\Z)',
            r'(?:User|USER).*?(?:wants|prefers|said).*?(?=\n\n|\Z)'
        ]
        for pattern in pref_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
            for m in matches[:1]:
                lessons['preferences'].append(m.strip()[:300])
        
        return lessons
        
    except Exception as e:
        return {'error': str(e)}

def append_to_master_files(lessons, source_date):
    """Append extracted lessons to master files"""
    
    # Append decisions
    if lessons.get('decisions'):
        with open(f"{MEMORY_DIR}/decisions.md", 'a') as f:
            f.write(f"\n## {source_date}\n")
            for d in lessons['decisions']:
                f.write(f"- {d}\n")
    
    # Append errors
    if lessons.get('errors'):
        with open(f"{MEMORY_DIR}/errors.md", 'a') as f:
            f.write(f"\n## {source_date}\n")
            for e in lessons['errors']:
                f.write(f"- {e}\n")
    
    # Update user preferences in USER.md
    if lessons.get('preferences'):
        with open(f"{MEMORY_DIR}/user_preferences_automatic.md", 'a') as f:
            f.write(f"\n## {source_date}\n")
            for p in lessons['preferences']:
                f.write(f"- {p}\n")

def compress_old_files():
    """Compress and archive files older than 7 days"""
    cutoff = datetime.now() - timedelta(days=7)
    compressed = 0
    space_saved = 0
    
    for filepath in Path(MEMORY_DIR).glob("*.md"):
        if filepath.name in ['MEMORY.md', 'decisions.md', 'errors.md']:
            continue
            
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        
        if mtime < cutoff:
            # Extract lessons before compression
            lessons = extract_key_lessons(str(filepath))
            append_to_master_files(lessons, mtime.strftime('%Y-%m-%d'))
            
            # Compress to archive
            date_str = mtime.strftime('%Y-%m')
            archive_file = f"{ARCHIVE_DIR}/{date_str}.jsonl.gz"
            
            with gzip.open(archive_file, 'at') as f:
                record = {
                    'date': mtime.isoformat(),
                    'file': filepath.name,
                    'lessons': lessons
                }
                f.write(json.dumps(record) + '\n')
            
            # Track space
            size = filepath.stat().st_size
            space_saved += size
            
            # Delete original
            filepath.unlink()
            compressed += 1
    
    return compressed, space_saved

def generate_skill_updates():
    """Check if enough patterns exist to update/create skills"""
    
    # Read decisions and errors
    patterns = {'decisions': 0, 'errors': 0}
    
    if os.path.exists(f"{MEMORY_DIR}/decisions.md"):
        with open(f"{MEMORY_DIR}/decisions.md", 'r') as f:
            content = f.read()
            patterns['decisions'] = content.count('## ')
    
    if os.path.exists(f"{MEMORY_DIR}/errors.md"):
        with open(f"{MEMORY_DIR}/errors.md", 'r') as f:
            content = f.read()
            patterns['errors'] = content.count('## ')
    
    # If enough patterns, suggest skill creation
    suggestions = []
    
    if patterns['errors'] > 10:
        suggestions.append("Consider creating 'common-errors' skill")
    
    if patterns['decisions'] > 15:
        suggestions.append("Consider creating 'decision-patterns' skill")
    
    return suggestions

def report_status():
    """Generate compression status report"""
    
    # Calculate sizes
    memory_size = sum(
        f.stat().st_size for f in Path(MEMORY_DIR).rglob('*') if f.is_file()
    )
    
    archive_size = sum(
        f.stat().st_size for f in Path(ARCHIVE_DIR).rglob('*') if f.is_file()
    ) if os.path.exists(ARCHIVE_DIR) else 0
    
    skills_count = len(list(Path(SKILLS_DIR).glob('*/SKILL.md')))
    
    report = f"""
╔══════════════════════════════════════════════════════════════════╗
║           MEMORY COMPRESSION STATUS                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Active Memory:    {memory_size / 1024 / 1024:.2f} MB                              ║
║  Archived:         {archive_size / 1024 / 1024:.2f} MB                              ║
║  Skills:           {skills_count}                                          ║
╚══════════════════════════════════════════════════════════════════╝
"""
    return report

def main():
    """Run compression cycle"""
    print("🔧 Memory Compression Daemon Starting...")
    
    setup_dirs()
    
    # Compress old files
    compressed, space_saved = compress_old_files()
    
    # Generate suggestions
    suggestions = generate_skill_updates()
    
    # Report
    print(report_status())
    
    if compressed > 0:
        print(f"✅ Compressed {compressed} files, saved {space_saved / 1024:.1f} KB")
    
    if suggestions:
        print("\n💡 Suggestions:")
        for s in suggestions:
            print(f"   - {s}")
    
    print("\n🔄 Compression complete")

if __name__ == "__main__":
    main()
