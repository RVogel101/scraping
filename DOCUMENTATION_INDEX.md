# Documentation Index & Navigation Guide

**Quick navigation for all Lousardzag project documentation.**

Find what you need fast. Updated March 3, 2026.

---

## 🎯 Start Here (First Time?)

### 1. **ARMENIAN_QUICK_REFERENCE.md** (2-3 min read)
The one-page cheat sheet. Start here for Armenian phonetics.

**What it covers**:
- Voicing reversal pattern (backwards from letter appearance)
- Context-aware letters table  
- Test words for verification
- Common mistakes
- Right vs. Wrong phonetic mapping

**When to use**: Before ANY phonetic work, every session

**Key section**: "⚠️ CRITICAL: The Voicing Reversal"

---

### 2. **NEXT_SESSION_INSTRUCTIONS.md** (10-15 min read)
Workflow guide with mandatory checklists and common commands.

**What it covers**:
- 10-minute checklist before phonetic work
- Project state summary
- Common commands (vocabulary generation, testing, previewing)
- Workflow for adding phonetic features
- Common mistakes & fixes
- Git workflow

**When to use**: Before starting each session, before any feature work

**Key sections**: 
- "Before You Do ANYTHING Phonetic-Related"
- "Common Mistakes & How to Fix Them"

---

## 📖 Complete References (1st Session + Deep Dives)

### 3. **WESTERN_ARMENIAN_PHONETICS_GUIDE.md** (Authoritative)
The complete, authoritative phoneme reference for Western Armenian.

**What it covers**:
- 38-letter complete phoneme map with IPA
- Voicing reversal principle explained with memorization tools
- Context-aware pronunciation rules for ո, ե, յ, ւ
- Diphthongs (ու, իւ)
- Difficulty scoring (1-5 scale)
- Common mistakes (Eastern Armenian defaults)
- Implementation checklist
- Testing guide with regression tests
- 200+ lines, heavily detailed

**When to use**: 
- When implementing phonetic features
- To verify a letter's correct IPA value
- When implementing context-aware phonetics
- As reference in code comments

**Key sections**:
- "Complete Western Armenian Phoneme Map (38 Letters)"
- "Context-Aware Pronunciation Rules"
- "Common Mistakes to Avoid (Checklist)"
- "Implementation Checklist"

**Related**: /memories/western-armenian-requirement.md (persistent copy)

---

### 4. **VOCABULARY_ORDERING_GUIDE.md** (System Architecture)
Complete documentation of vocabulary ordering, batching, and proficiency systems.

**What it covers**:
- 5 ordering modes: frequency, pos_frequency, band_pos_frequency, difficulty, difficulty_band
- 3 batch strategies: fixed, growth, banded
- 4 presets: l1-core, l2-expand, l3-bridge, n-standard
- N1-N7 proficiency system (JLPT-style)
- Output CSV column specifications
- Common use cases with command examples
- Data quality & filtering
- Validation checklist
- 300+ lines

**When to use**:
- When generating vocabulary
- To understand preset differences
- To create custom ordering configurations
- For validation after generation
- Understanding proficiency levels

**Key sections**:
- "Ordering Modes (5 Total)"
- "Batch Strategies (3 Total)"
- "Proficiency Block System"
- "Presets (Pre-Configured Combinations)"
- "Common Use Cases"

---

### 5. **PROJECT_ASSESSMENT.md** (Current State)
Comprehensive assessment of project status, what's working, what needs work.

**What it covers**:
- Current state overview (what's working, what's not)
- Test coverage (323 tests passing)
- Branch status
- Next session recommendations (Tier 1-4)
- Project metrics
- Code quality assessment
- Timeline estimates
- Decision points for next work
- Critical knowledge to remember

**When to use**:
- At start of session (understand what's already done)
- To decide what to work on next
- To understand project maturity level
- For context on incomplete features

**Key sections**:
- "What's Working" / "What's Missing"
- "Next Session Recommendations (Tier 1-4)"
- "Critical Knowledge to Remember"

---

## 🔍 For Specific Tasks

### Task: Work on Armenian Phonetics
**Start**: ARMENIAN_QUICK_REFERENCE.md (5 min)
→ NEXT_SESSION_INSTRUCTIONS.md § "Workflow: Adding Phonetic Feature" (5 min)
→ WESTERN_ARMENIAN_PHONETICS_GUIDE.md (reference as needed)

### Task: Generate or Modify Vocabulary
**Start**: NEXT_SESSION_INSTRUCTIONS.md § "Common Commands" (2 min)
→ VOCABULARY_ORDERING_GUIDE.md § "Common Use Cases" (3 min)
→ VOCABULARY_ORDERING_GUIDE.md (full reference as needed)

### Task: Fix a Bug or Implement a Feature
**Start**: PROJECT_ASSESSMENT.md § "Code Quality Assessment" (2 min)
→ NEXT_SESSION_INSTRUCTIONS.md § "Git Workflow" (3 min)
→ Appropriate complete guide (phonetics or vocabulary)

### Task: Understand Project State
**Start**: PROJECT_ASSESSMENT.md (10-15 min read)
→ Branch status, working systems, incomplete features

### Task: Decide What to Work On Next
**Start**: PROJECT_ASSESSMENT.md § "Next Session Recommendations" (5 min)
→ Understand Tier 1-4 priorities
→ NEXT_SESSION_INSTRUCTIONS.md § "Session Template" (2 min)
→ Dive into chosen task's complete guide

---

## 📋 By Audience

### For New Contributors
1. Read PROJECT_ASSESSMENT.md (understand current state)
2. Read ARMENIAN_QUICK_REFERENCE.md (phonetics primer)
3. Read NEXT_SESSION_INSTRUCTIONS.md (workflow guidelines)
4. Choose task from PROJECT_ASSESSMENT.md Tier 1-2
5. Reference WESTERN_ARMENIAN_PHONETICS_GUIDE.md or VOCABULARY_ORDERING_GUIDE.md as needed

### For Returning Contributors
1. Read NEXT_SESSION_INSTRUCTIONS.md § "Project State Summary" (2 min)
2. Run mandatory checklist (10 min)
3. Pick up where you left off
4. Reference guides as needed

### For Project Reviewers
1. Read PROJECT_ASSESSMENT.md (full project overview)
2. Check git history: `git log --oneline -20`
3. Run tests: `python -m pytest 04-tests/ -q`
4. Review specific files in 02-src/lousardzag/ or 07-tools/

### For Phonetics Specialists
1. Read WESTERN_ARMENIAN_PHONETICS_GUIDE.md (authoritative reference)
2. Check 02-src/lousardzag/phonetics.py (implementation)
3. Review test cases in 04-tests/integration/test_transliteration.py
4. Implement improvements; commit with scope `feat(phonetics):` or `fix(phonetics):`

### For Curriculum Developers
1. Read VOCABULARY_ORDERING_GUIDE.md (complete system)
2. Explore 08-data/ for example outputs (vocab_n_standard.csv, etc.)
3. Read NEXT_SESSION_INSTRUCTIONS.md § "Common Commands"
4. Generate test vocabularies with different presets/configurations
5. Use HTML preview (vocabulary_preview.html) for interactive review

---

## 🔗 Cross-References

### When Reading About...

**Western Armenian Phonetics**
- Quick lookup → ARMENIAN_QUICK_REFERENCE.md
- Complete reference → WESTERN_ARMENIAN_PHONETICS_GUIDE.md
- Implementation → 02-src/lousardzag/phonetics.py
- Persistent memory → /memories/western-armenian-requirement.md
- Tests → 04-tests/integration/test_transliteration.py

**Vocabulary Ordering**
- Quick reference → NEXT_SESSION_INSTRUCTIONS.md § "Common Commands"
- Complete system → VOCABULARY_ORDERING_GUIDE.md
- Implementation → 07-tools/gen_vocab_simple.py
- Example outputs → 08-data/vocab_*.csv files
- Preview → 08-data/vocabulary_preview.html

**Project Status**
- Overview → PROJECT_ASSESSMENT.md
- Next work → PROJECT_ASSESSMENT.md § "Next Session Recommendations"
- Workflow → NEXT_SESSION_INSTRUCTIONS.md
- Git history → `git log --oneline -20`

**Critical Knowledge**
- Voicing reversal → ARMENIAN_QUICK_REFERENCE.md § "Voicing Reversal"
- Context-aware letters → ARMENIAN_QUICK_REFERENCE.md § "Context-Aware Letters"
- Test words → ARMENIAN_QUICK_REFERENCE.md § "Test Words"
- All three in detail → WESTERN_ARMENIAN_PHONETICS_GUIDE.md

---

## 📊 Documentation Matrix

| Document | Purpose | Audience | Read Time | When to Use |
|----------|---------|----------|-----------|------------|
| ARMENIAN_QUICK_REFERENCE.md | Quick lookup, cheat sheet | Everyone | 2-3 min | Every session start |
| NEXT_SESSION_INSTRUCTIONS.md | Workflow guide, checklists | All contributors | 10-15 min | Session start, new task |
| WESTERN_ARMENIAN_PHONETICS_GUIDE.md | Complete phonetics reference | Phonetics implementers | 30-45 min | Deep phonetic work |
| VOCABULARY_ORDERING_GUIDE.md | Complete system architecture | Vocab/curriculum developers | 30-45 min | Vocabulary generation/mods |
| PROJECT_ASSESSMENT.md | Current state, roadmap | Decision makers | 15-20 min | Quarterly review, planning |
| This file (DOCUMENTATION_INDEX.md) | Navigation guide | Everyone (finding things) | 5-10 min | Finding documentation |

---

## 📁 File System Map

```
lousardzag/
├── ARMENIAN_QUICK_REFERENCE.md          ← START HERE (2-3 min)
├── NEXT_SESSION_INSTRUCTIONS.md         ← WORKFLOW GUIDE (10-15 min)
├── WESTERN_ARMENIAN_PHONETICS_GUIDE.md  ← PHONETICS REFERENCE (30-45 min)
├── VOCABULARY_ORDERING_GUIDE.md         ← VOCAB SYSTEM (30-45 min)
├── PROJECT_ASSESSMENT.md                ← PROJECT STATE (15-20 min)
├── DOCUMENTATION_INDEX.md               ← YOU ARE HERE
│
├── 02-src/lousardzag/
│   ├── phonetics.py                     (200+ lines, implementation)
│   ├── database.py                      (vocabulary metadata)
│   └── [other modules]
│
├── 07-tools/
│   ├── gen_vocab_simple.py              (570+ lines, vocab generation)
│   ├── generate_ordered_cards.py        (card generation)
│   └── [analysis scripts]
│
├── 04-tests/
│   ├── test_card_generator.py
│   ├── test_integration.py
│   ├── unit/test_difficulty.py          (28+ phonetics tests)
│   ├── unit/test_*_verbs.py
│   └── integration/test_transliteration.py (60+ tests)
│
├── 08-data/
│   ├── vocab_n_standard.csv             (140 words, example output)
│   ├── vocab_l1_core.csv                (60 words)
│   ├── vocabulary_preview.html          (interactive preview)
│   └── [other data files]
│
├── .github/
│   └── copilot-instructions.md          (project guidelines)
│
├── /memories/
│   └── western-armenian-requirement.md  (persistent reference)
│
└── README.md                            (project overview)
```

---

## 🔄 Reading Workflows

### "I have 5 minutes"
1. ARMENIAN_QUICK_REFERENCE.md (2 min)
2. Run tests: `python -m pytest 04-tests/ -q` (3 min)

### "I have 15 minutes"
1. ARMENIAN_QUICK_REFERENCE.md (2 min)
2. NEXT_SESSION_INSTRUCTIONS.md § overview sections (5 min)
3. PROJECT_ASSESSMENT.md § "Current State Overview" (5 min)
4. Choose Tier 1 task to start (3 min)

### "I have 30 minutes"
1. Complete "I have 15 minutes" (15 min)
2. Task-specific guide § relevant section (10 min)
3. Start implementation (5 min)

### "I have an hour"
1. PROJECT_ASSESSMENT.md (full) (20 min)
2. NEXT_SESSION_INSTRUCTIONS.md (full) (15 min)
3. Task-specific guide § key sections (15 min)
4. Begin implementation, reference as needed (10 min)

---

## 📞 Finding Help

**"Where do I look for...?"**

| Need | Document | Section |
|------|----------|---------|
| Voicing reversal explanation | ARMENIAN_QUICK_REFERENCE.md | "⚠️ CRITICAL" |
| Which preset to use | VOCABULARY_ORDERING_GUIDE.md | "Common Use Cases" |
| How to fix Eastern Armenian error | NEXT_SESSION_INSTRUCTIONS.md | "Mistake 1: Eastern Armenian" |
| Complete IPA reference | WESTERN_ARMENIAN_PHONETICS_GUIDE.md | "Complete Phoneme Map" |
| What's been done | PROJECT_ASSESSMENT.md | "What's Working" |
| What to do next | PROJECT_ASSESSMENT.md | "Next Session Recommendations" |
| Git workflow | NEXT_SESSION_INSTRUCTIONS.md | "Git Workflow" |
| Vocabulary output format | VOCABULARY_ORDERING_GUIDE.md | "Output CSV Format" |
| Test word verification | ARMENIAN_QUICK_REFERENCE.md | "Test Words" |
| Context-aware phonemes | WESTERN_ARMENIAN_PHONETICS_GUIDE.md | "Context-Aware Pronunciation" |

---

## 🎓 Learning Paths

### Path 1: Phonetics Specialist
- ARMENIAN_QUICK_REFERENCE.md (2 min)
- WESTERN_ARMENIAN_PHONETICS_GUIDE.md (full, 45 min)
- 02-src/lousardzag/phonetics.py (code review, 30 min)
- 04-tests/integration/test_transliteration.py (test review, 20 min)
- Start implementing: context-aware letters or additional diphthongs
- **Total**: ~2 hours

### Path 2: Curriculum Developer
- ARMENIAN_QUICK_REFERENCE.md (2 min)
- VOCABULARY_ORDERING_GUIDE.md (full, 45 min)
- Explore 08-data/ outputs (15 min)
- NEXT_SESSION_INSTRUCTIONS.md § "Common Commands" (5 min)
- Generate test vocabularies (30 min)
- Create custom preset (30 min)
- **Total**: ~2 hours

### Path 3: Feature Developer
- PROJECT_ASSESSMENT.md (20 min)
- NEXT_SESSION_INSTRUCTIONS.md (full, 15 min)
- Task-specific guide (30 min)
- Code review of relevant module (20 min)
- Implement feature (60+ min)
- Test and commit (30 min)
- **Total**: 3+ hours

### Path 4: Code Reviewer
- PROJECT_ASSESSMENT.md § "Code Quality" (10 min)
- Skim NEXT_SESSION_INSTRUCTIONS.md (5 min)
- git log review (5 min)
- Test run (5 min)
- Code review of specific module (30+ min)
- **Total**: 1+ hours

---

## ✅ Documentation Maintenance

### Last Updates
- **ARMENIAN_QUICK_REFERENCE.md**: March 3, 2026
- **NEXT_SESSION_INSTRUCTIONS.md**: March 3, 2026
- **WESTERN_ARMENIAN_PHONETICS_GUIDE.md**: March 3, 2026
- **VOCABULARY_ORDERING_GUIDE.md**: March 3, 2026
- **PROJECT_ASSESSMENT.md**: March 3, 2026
- **DOCUMENTATION_INDEX.md**: March 3, 2026

### Adding New Documentation

When you add a new feature:
1. Create focused documentation file (e.g., FEATURE_GUIDE.md)
2. Add cross-reference in relevant existing documents
3. Update DOCUMENTATION_INDEX.md with new entry
4. Commit documentation with feature code
5. Update the "Last Updates" section above

---

## 🚀 Quick Start (TL;DR)

1. **Read this**: ARMENIAN_QUICK_REFERENCE.md (2 min)
2. **Read this**: NEXT_SESSION_INSTRUCTIONS.md (10 min)
3. **Do this**: Run checklist in NEXT_SESSION_INSTRUCTIONS.md (10 min)
4. **Read as needed**: WESTERN_ARMENIAN_PHONETICS_GUIDE.md or VOCABULARY_ORDERING_GUIDE.md
5. **Reference**: PROJECT_ASSESSMENT.md to decide what to work on

**Total setup time**: 20-30 minutes for a new session

---

**Navigation Guide Updated**: March 3, 2026  
**Project**: Lousardzag (Western Armenian Learning Platform)  
**Branch**: pr/copilot-swe-agent/2
