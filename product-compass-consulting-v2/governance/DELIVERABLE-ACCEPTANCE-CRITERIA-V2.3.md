---
document_type: governance
version: V2.3
status: approved
supersedes: V2.2
---

# Deliverable Acceptance Criteria V2.3

Quantifiable quality gates for all Phase A/B/C deliverables. No more "feels right" reviews.

> **Scope note (V2.2)**: Document-level gates (C1–C8) passing does NOT imply project-level
> acceptance. A deliverable may be individually perfect yet misplaced. Project-level structure
> governance is covered by **C8** and must pass before the phase is closed.
>
> **Reviewer language note (V2.3)**: The board reviewer (峰哥) reads Chinese. All core
> deliverables MUST be in Simplified Chinese so they can be reviewed. English-only output is a
> hard reject (C9).

## Project Root & Phase Launch Convention (V2.2)

All Phase A/B/C deliverables for GEO119 live under the **agreed project root**:

```
/media/ok2049/work/work/AMM/GEO/geo119/
```

- The Paperclip `managedFolder` (`_default/`) is **staging only** — agents write there
  during execution, but the canonical deliverables MUST be placed (or synced) under the
  project root. Final acceptance (C8) is checked against the project root, not managedFolder.
- **Launch requirement**: Every Phase launch — whether driven by a skill OR a raw prompt —
  MUST explicitly state the output root. The location convention is a hard launch input,
  not an agent's discretion.
- **Language requirement (V2.3)**: Every Phase launch MUST also state the deliverable language
  (Simplified Chinese for core deliverables). Omitting it is the root cause of unreadable output.

## P0 Criteria (Must All Pass — Any Single Failure = Reject)

### C1: SEO Misrepresentation Zero
- **Threshold**: 0 findings where GEO119 itself is described as / positioned as an SEO tool or service
- **Check**: grep for patterns indicating the *product* is described as SEO
- **Command**: `grep -rni "SEO" --include="*.md" . | grep -v "GEO119\|GEO\|acceptance-criteria\|governance"`
- **Intent clarification (V2.2)**: Forbids misrepresenting *GEO119's own value/framing* as SEO.
  Does NOT forbid "SEO" in legitimate contexts (competitive landscape, persona backgrounds,
  market pain). Reviewers must read each match in context before rejecting.

### C2: GEO/SEO Conflation Zero
- **Threshold**: 0 occurrences of "SEO/GEO" or "SEO and GEO" used interchangeably as one concept
- **Check**: GEO119 never described as an SEO tool; "SEO" and "GEO" never the same thing.
  "SEO/GEO specialist" is a conflation → rewrite "AI search optimization specialist".
- **Command**: `grep -rni "SEO.GEO\|SEO and GEO\|SEO & GEO" --include="*.md" .`

### C3: Core Fact Consistency
- **Threshold**: 0 inconsistencies across all deliverables
- **Facts**: Language=119 languages, Product name=GEO119, Positioning=AI Search Optimization, Business model=Prepaid, V1 Market=Vietnam
- **Check**: Manual review of core facts in each deliverable

### C4: Deliverable Completeness
- **Threshold**: All expected files exist AND each file > 200 bytes
- **Check**: `find . -name "*.md" -size -201c` returns empty
- **Check**: Expected deliverable list matches actual files

### C7: Version Consistency
- **Threshold**: Final version line count ≥ draft version line count
- **Check**: For each file in 01-strategy/, verify line count ≥ corresponding file in 00-plans/ (if exists)

### C8: Structure Governance (V2.2 — P0)
- **C8a — Layer Placement**: Each core deliverable resides in the directory matching its real layer
  (strategy→`01-strategy/`, users→`02-users/`, dev→`03-development/`, ops→`04-operations/`,
  brand→`05-brand/`, GTM/marketing/growth→dedicated layers, never stuffed in `01-strategy/`).
- **C8b — Frontmatter Integrity**: `directory:` frontmatter must equal actual physical path.
- **C8c — Zero Broken Links**: After any move/rename, all relative links resolve (0 broken).
- **C8d — Plan/Structure Alignment**: Final tree matches the Phase Plan document.
- **C8e — Output Root Compliance**: All 18 core deliverables exist under the project root, not
  solely in managedFolder.
- **C8f — No Process Artifacts in Core Dirs (V2.3)**: Core-layer directories (`01-strategy/`,
  `02-users/`, etc.) contain ONLY final deliverables. Planning/review/verification/risk/master
  artifacts MUST live in a separate `00-process/` directory. Any `*-plan.md`, `*-review.md`,
  `*-verification.md`, `risk-*.md`, `*-master-plan.md` found inside a core deliverable directory
  = C8f fail.

### C9: Language Compliance — Simplified Chinese (V2.3 — P0)
All **core deliverables** must be written in Simplified Chinese so the board can review them.
- **Threshold**: 0 core deliverables predominantly in a non-Chinese language
- **Applies to**: the 18 (or current phase's) core deliverables, NOT process artifacts in `00-process/`
- **Allowed in English**: proper nouns, product/brand names (GEO119), technical terms with
  established Chinese equivalents noted, code blocks, bibliographic references, and explicitly
  quoted foreign text. These do not fail the gate.
- **Check**: open each core deliverable; if the body prose is predominantly English (e.g. headings,
  paragraphs, table content are English), it fails. A mostly-Chinese doc with English terms sprinkled
  passes.
- **Command (heuristic, not sufficient alone)**: `grep -c "[\x{4e00}-\x{9fff}]" <file>` should return
  a count indicating substantial Chinese presence; combine with manual read.

## P1 Criteria (Must Pass or Document as Known Limitation)

### C5: Semantic Quality
- **Threshold**: At least 3 h2 sections (##), ≥200 bytes per section, no placeholder text
- **Check**: `grep -c "^## " <file>` returns ≥ 3
- **Check**: No "TBD", "TODO", "lorem ipsum", "placeholder", "coming soon"
  (substring matches inside legitimate acronyms like "JTBD" are NOT placeholders)

### C6: Link Validity
- **Threshold**: 0 broken internal links
- **Check**: All relative markdown links `[text](./path/to/file.md)` point to existing files

## Pass/Fail Rules

| Status | Condition |
|--------|-----------|
| **PASS** | All 7 P0 criteria pass (C1, C2, C3, C4, C7, C8, C9) AND all 2 P1 criteria pass (C5, C6) |
| **CONDITIONAL PASS** | All 7 P0 criteria pass, P1 failures documented with reason |
| **FAIL** | Any P0 criterion fails |

## Running Validation

```bash
bash governance/acceptance_check.sh
```
