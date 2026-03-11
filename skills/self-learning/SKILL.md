---
name: self-learning
description: Continuous learning, skill improvement, and knowledge acquisition system. Use when the user wants me to learn from experiences, improve my capabilities, study new domains, make better decisions over time, or build institutional knowledge. Triggers on requests about learning, improving, studying, getting better, or developing new capabilities.
---

# Self-Learning & Continuous Improvement System

A structured approach to learning from every interaction, improving decision-making, and building institutional knowledge over time.

## Core Principles

1. **Every interaction is a learning opportunity**
2. **Document what works and what fails**
3. **Build patterns from successes**
4. **Analyze failures without blame**
5. **Update mental models continuously**

## Learning Process

### 1. Capture (During Interaction)

When working on tasks, actively capture:
- What was the actual problem vs. assumed problem?
- What approach worked? What failed?
- What was unexpected?
- What would I do differently?

**Immediate captures go to:** `memory/YYYY-MM-DD.md`

### 2. Distill (End of Session)

Before session ends, review captures and extract:
- Key lessons (1-3 per session)
- Updated heuristics
- New patterns to remember
- Corrections to prior assumptions

**Distilled learning goes to:** `AGENTS.md`, `TOOLS.md`, or `SOUL.md`

### 3. Synthesize (Weekly)

During heartbeat checks, review recent memory files:
- Identify recurring themes
- Update long-term patterns
- Consolidate scattered insights
- Remove outdated knowledge

**Synthesized knowledge goes to:** `MEMORY.md`

### 4. Apply (Next Interaction)

Before starting work:
- Check relevant memory for prior context
- Apply learned patterns
- Avoid repeated mistakes
- Reference previous solutions

## Decision-Making Improvement

### Decision Log Format

```markdown
## Decision: [Brief description]
**Date:** YYYY-MM-DD
**Context:** What was happening
**Options Considered:**
1. Option A - why
2. Option B - why
**Decision:** Chosen option
**Reasoning:** Why this choice
**Expected Outcome:** What I thought would happen
**Actual Outcome:** (filled in later)
**Lesson:** What to remember
```

### Decision Review Triggers

- When outcome differs significantly from expectation
- When user corrects my approach
- When I discover a better way after the fact
- When same situation recurs with different choice

## Skill Development Process

### When Learning New Domains

1. **First exposure:** Capture everything, don't worry about organization
2. **Second use:** Identify patterns, create initial heuristics  
3. **Third use:** Build structured knowledge, update SKILL.md if applicable
4. **Ongoing:** Refine based on edge cases and failures

### Skill Level Tracking

Track proficiency in `memory/skills/`:

```markdown
# Skill: [Name]
**Level:** Novice | Competent | Proficient | Expert
**First Used:** YYYY-MM-DD
**Times Used:** N

## What I Know
- Core concepts
- Common patterns
- Typical pitfalls

## What I'm Learning
- Recent insights
- Areas of uncertainty
- Questions to answer

## Failure Log
- What went wrong
- Why it went wrong
- How to avoid next time
```

## Error Analysis Protocol

### When Things Go Wrong

1. **Immediate:** Fix the problem (don't analyze yet)
2. **After fix:** Document what happened
3. **Same day:** Analyze root cause
4. **Next occurrence:** Reference prior analysis

### Error Categories

- **Knowledge gap:** I didn't know something
- **Reasoning error:** I knew but reasoned wrong
- **Execution error:** I knew and reasoned right but implemented wrong
- **Context error:** I didn't have enough context
- **Assumption error:** I assumed incorrectly

## Continuous Improvement Checklist

### Daily (During Session)
- [ ] Capture unexpected outcomes
- [ ] Note user corrections
- [ ] Document working solutions

### Weekly (During Heartbeat)
- [ ] Review memory files from past 7 days
- [ ] Identify patterns and themes
- [ ] Update long-term memory
- [ ] Consolidate learnings

### Monthly (Proactive)
- [ ] Review skill proficiency levels
- [ ] Identify knowledge gaps
- [ ] Plan learning goals
- [ ] Archive outdated information

## Meta-Learning Heuristics

1. **The user is always right about the problem** - Even when wrong about the solution
2. **Simple beats clever** - Unless proven otherwise by evidence
3. **Ask sooner** - Ambiguity costs more than questions
4. **Verify assumptions** - Especially "obvious" ones
5. **Document the why** - Not just the what
6. **Failures teach more** - When analyzed honestly
7. **Patterns emerge slowly** - Don't force them early
8. **Context is everything** - Solutions don't transfer blindly

## Learning Triggers

Activate this skill when:
- User says "learn from this"
- User corrects my approach
- I encounter something completely new
- I make an error
- User asks me to improve
- I notice I'm repeating myself
- Outcome differs from expectation
- User says "remember this"

## Output Locations

| Content | Location | When |
|---------|----------|------|
| Raw captures | `memory/YYYY-MM-DD.md` | Immediate |
| Skill updates | `AGENTS.md`, `SOUL.md` | End of session |
| Tool notes | `TOOLS.md` | When tool behavior learned |
| Long-term memory | `MEMORY.md` | Weekly synthesis |
| Skill proficiency | `memory/skills/*.md` | When skill used |
| Decision log | `memory/decisions.md` | When significant decision made |
| Error log | `memory/errors.md` | When errors occur |

## Quality Metrics

Track learning effectiveness:
- **Same mistake twice?** Log it, analyze why pattern didn't stick
- **User repeating instructions?** I failed to learn, fix capture process
- **Faster on repeated tasks?** Learning is working
- **Better outcomes over time?** Improvement is real
