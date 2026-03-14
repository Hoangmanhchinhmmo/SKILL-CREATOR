---
name: kaigai-script-writer
description: "Create viral YouTube voice-over scripts in Japanese '海外の反応' style. Use when user wants to research trending topics, suggest viral content ideas, or write TTS-optimized scripts for Japanese audiences. Triggers: kaigai, 海外の反応, YouTube script, viral topic, voice over, script writer."
category: content
risk: safe
source: community
tags: "[youtube, japanese, kaigai, script, tts, viral, 海外の反応]"
date_added: "2025-01-01"
---

# Kaigai Script Writer - 海外の反応スクリプトライター

## Purpose

Create viral YouTube voice-over scripts in Japanese "海外の反応" (overseas reactions) style. Full workflow: research trending topics → suggest viral content → write TTS-optimized scripts → output to files.

## When to Use This Skill

- User wants to find viral topics for Japanese YouTube audience
- User wants to create "海外の反応" style video scripts
- User wants to write Japanese voice-over scripts optimized for TTS
- User mentions: kaigai, 海外の反応, YouTube script, viral topic, voice over, kịch bản, script writer

## Do not use this skill when

- User wants general translation (not script writing)
- User wants non-YouTube content creation
- User wants video editing or production tasks

## Instructions

Read and apply ALL instructions from the core logic file: `../core/kaigai-core.md`

The core file contains the complete system: identity, workflow, viral scorecard, emotional arc blueprint, chain of thought writing process, TTS rules, output format, and quality rules.

### Workflow Summary

1. **NICHE** → Ask user to choose content niche (default: MLB/Ohtani)
2. **SEARCH** → Use WebSearch/WebFetch if available, or ask user for input
3. **SUGGEST** → Present topic candidates with Viral Score, wait for selection
4. **WRITE** → Apply Chain of Thought (PLAN → WRITE → SELF-CHECK) for each section
5. **OUTPUT** → Save `./XXX-slug/metadata.md` + `./XXX-slug/voiceover.txt`

### Key Rules

- Communicate in **Vietnamese**, output in **Japanese**
- Follow **Emotional Arc Blueprint** for script flow
- Apply **TTS hard limits**: sentence ≤60 chars, ideal 30–50 chars
- Use **Viral Scorecard** (10-point) to evaluate topics
- Run **Self-Check** before outputting each script section
- **NEVER fabricate** quotes, statistics, or media reactions

### 表記規則 — Notation Rules (MANDATORY)

- **NO English in scripts** — all English must be replaced with katakana/Japanese equivalents
- **Japanese names & places** → kanji (with hiragana furigana on first appearance if uncommon)
- **Foreign proper nouns** → katakana (e.g., ボーイング, マイク・トラウト, シーエヌエヌ)
- **Foreign countries & continents** → katakana (e.g., アメリカ, アジア, ヨーロッパ)
- **All numbers** → Arabic numerals (e.g., 2024年, 28歳, 50000人, 1000円)
- **Abbreviations** → katakana pronunciation (ESPN → イーエスピーエヌ, MLB → メジャーリーグ)

### 文体規則 — Authentic Japanese Style (MANDATORY)

- Write in authentic Japanese — NOT translated from Vietnamese/English
- Follow SOV structure naturally with correct particles
- Use です/ます consistently (polite but not overly formal)
- Alternate short (20-30 chars) and medium (35-50 chars) sentences for TTS rhythm
- Use native Japanese expressions (日本語らしい表現) instead of literal translations
- Vary sentence endings — never repeat same pattern >2 times consecutively

### File Output

- Scan CWD for existing `XXX-*` folders → next number
- Create `./XXX-slug/metadata.md` (titles, thumbnails, structure)
- Create `./XXX-slug/voiceover.txt` (plain text Japanese script, TTS-ready)

## References

- Core logic: [kaigai-core.md](../core/kaigai-core.md)
