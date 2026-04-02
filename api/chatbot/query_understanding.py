"""
ParcFermé AI — Query Understanding Layer.

Sits between the user prompt and the retrieval/agent loop.
Performs:
  1. LLM-powered intent + entity extraction (general common-sense)
  2. Confidence / ambiguity scoring
  3. Telemetry required-field enforcement
  4. Assumption budget enforcement (max 1 unverified assumption)
  5. Clarification template generation
  6. Post-answer validation checklist
"""

from __future__ import annotations

import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Confidence thresholds ───────────────────────────────────────────────
HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.50

# ── Well-known F1 alias registry (seed for LLM fallback) ───────────────
# The LLM handles anything not here, but this gives deterministic fast
# resolution for the most common abbreviations without an LLM call.
DRIVER_ALIASES: Dict[str, Tuple[str, str]] = {
    # Hamilton
    "HAM": ("DRV_HAM", "Lewis Hamilton"),
    "LEW": ("DRV_HAM", "Lewis Hamilton"),
    "LEWIS": ("DRV_HAM", "Lewis Hamilton"),
    "HAMILTON": ("DRV_HAM", "Lewis Hamilton"),
    # Verstappen
    "VER": ("DRV_VER", "Max Verstappen"),
    "MAX": ("DRV_VER", "Max Verstappen"),
    "VERSTAPPEN": ("DRV_VER", "Max Verstappen"),
    # Norris
    "NOR": ("DRV_NOR", "Lando Norris"),
    "LANDO": ("DRV_NOR", "Lando Norris"),
    "NORRIS": ("DRV_NOR", "Lando Norris"),
    # Leclerc
    "LEC": ("DRV_LEC", "Charles Leclerc"),
    "LECLERC": ("DRV_LEC", "Charles Leclerc"),
    "CHARLES": ("DRV_LEC", "Charles Leclerc"),
    # Piastri
    "PIA": ("DRV_PIA", "Oscar Piastri"),
    "PIASTRI": ("DRV_PIA", "Oscar Piastri"),
    "OSCAR": ("DRV_PIA", "Oscar Piastri"),
    # Russell
    "RUS": ("DRV_RUS", "George Russell"),
    "RUSSELL": ("DRV_RUS", "George Russell"),
    "GEORGE": ("DRV_RUS", "George Russell"),
    # Antonelli
    "ANT": ("DRV_ANT", "Kimi Antonelli"),
    "ANTONELLI": ("DRV_ANT", "Kimi Antonelli"),
    "KIMI": ("DRV_ANT", "Kimi Antonelli"),
    # Alonso
    "ALO": ("DRV_ALO", "Fernando Alonso"),
    "ALONSO": ("DRV_ALO", "Fernando Alonso"),
    "FERNANDO": ("DRV_ALO", "Fernando Alonso"),
    # Stroll
    "STR": ("DRV_STR", "Lance Stroll"),
    "STROLL": ("DRV_STR", "Lance Stroll"),
    # Albon
    "ALB": ("DRV_ALB", "Alex Albon"),
    "ALBON": ("DRV_ALB", "Alex Albon"),
    # Sainz
    "SAI": ("DRV_SAI", "Carlos Sainz"),
    "SAINZ": ("DRV_SAI", "Carlos Sainz"),
    "CARLOS": ("DRV_SAI", "Carlos Sainz"),
    # Gasly
    "GAS": ("DRV_GAS", "Pierre Gasly"),
    "GASLY": ("DRV_GAS", "Pierre Gasly"),
    # Colapinto
    "COL": ("DRV_COL", "Franco Colapinto"),
    "COLAPINTO": ("DRV_COL", "Franco Colapinto"),
    # Ocon
    "OCO": ("DRV_OCO", "Esteban Ocon"),
    "OCON": ("DRV_OCO", "Esteban Ocon"),
    # Bearman
    "BEA": ("DRV_BEA", "Oliver Bearman"),
    "BEARMAN": ("DRV_BEA", "Oliver Bearman"),
    # Hülkenberg
    "HUL": ("DRV_HUL", "Nico Hülkenberg"),
    "HULKENBERG": ("DRV_HUL", "Nico Hülkenberg"),
    # Bortoleto
    "BOR": ("DRV_BOR", "Gabriel Bortoleto"),
    "BORTOLETO": ("DRV_BOR", "Gabriel Bortoleto"),
    # Lawson
    "LAW": ("DRV_LAW", "Liam Lawson"),
    "LAWSON": ("DRV_LAW", "Liam Lawson"),
    # Lindblad
    "LIN": ("DRV_LIN", "Arvid Lindblad"),
    "LINDBLAD": ("DRV_LIN", "Arvid Lindblad"),
    # Hadjar
    "HAD": ("DRV_HAD", "Isack Hadjar"),
    "HADJAR": ("DRV_HAD", "Isack Hadjar"),
    # Pérez
    "PER": ("DRV_PER", "Sergio Pérez"),
    "PEREZ": ("DRV_PER", "Sergio Pérez"),
    "CHECO": ("DRV_PER", "Sergio Pérez"),
    # Bottas
    "BOT": ("DRV_BOT", "Valtteri Bottas"),
    "BOTTAS": ("DRV_BOT", "Valtteri Bottas"),
    # Historical (common references)
    "VETTEL": ("DRV_VET", "Sebastian Vettel"),
    "SEB": ("DRV_VET", "Sebastian Vettel"),
    "SCHUMACHER": ("DRV_MSC", "Michael Schumacher"),
    "SENNA": ("DRV_SEN", "Ayrton Senna"),
    "PROST": ("DRV_PRO", "Alain Prost"),
    "RAIKKONEN": ("DRV_RAI", "Kimi Räikkönen"),
    "RICCIARDO": ("DRV_RIC", "Daniel Ricciardo"),
    "DANNY RIC": ("DRV_RIC", "Daniel Ricciardo"),
}

# ── GP / Circuit aliases ───────────────────────────────────────────────
GP_ALIASES: Dict[str, str] = {
    "MONZA": "Italian Grand Prix",
    "SPA": "Belgian Grand Prix",
    "SILVERSTONE": "British Grand Prix",
    "MONACO": "Monaco Grand Prix",
    "SUZUKA": "Japanese Grand Prix",
    "INTERLAGOS": "São Paulo Grand Prix",
    "BRAZIL": "São Paulo Grand Prix",
    "JEDDAH": "Saudi Arabian Grand Prix",
    "BAHRAIN": "Bahrain Grand Prix",
    "ALBERT PARK": "Australian Grand Prix",
    "MELBOURNE": "Australian Grand Prix",
    "MIAMI": "Miami Grand Prix",
    "IMOLA": "Emilia Romagna Grand Prix",
    "BARCELONA": "Spanish Grand Prix",
    "MONTREAL": "Canadian Grand Prix",
    "CANADA": "Canadian Grand Prix",
    "SINGAPORE": "Singapore Grand Prix",
    "MARINA BAY": "Singapore Grand Prix",
    "YAS MARINA": "Abu Dhabi Grand Prix",
    "ABU DHABI": "Abu Dhabi Grand Prix",
    "SHANGHAI": "Chinese Grand Prix",
    "CHINA": "Chinese Grand Prix",
    "AUSTIN": "United States Grand Prix",
    "COTA": "United States Grand Prix",
    "ZANDVOORT": "Dutch Grand Prix",
    "HUNGARY": "Hungarian Grand Prix",
    "BUDAPEST": "Hungarian Grand Prix",
    "HUNGARORING": "Hungarian Grand Prix",
    "BAKU": "Azerbaijan Grand Prix",
    "AZERBAIJAN": "Azerbaijan Grand Prix",
    "LAS VEGAS": "Las Vegas Grand Prix",
    "VEGAS": "Las Vegas Grand Prix",
    "QATAR": "Qatar Grand Prix",
    "LOSAIL": "Qatar Grand Prix",
    "MEXICO": "Mexico City Grand Prix",
    "MEXICO CITY": "Mexico City Grand Prix",
}

# ── Session aliases ─────────────────────────────────────────────────────
SESSION_ALIASES: Dict[str, str] = {
    "FP1": "Free Practice 1",
    "FP2": "Free Practice 2",
    "FP3": "Free Practice 3",
    "PRACTICE": "Free Practice",
    "QUALI": "Qualifying",
    "QUALIFYING": "Qualifying",
    "Q1": "Qualifying Q1",
    "Q2": "Qualifying Q2",
    "Q3": "Qualifying Q3",
    "RACE": "Race",
    "SPRINT": "Sprint",
    "SPRINT QUALI": "Sprint Qualifying",
    "SQ": "Sprint Qualifying",
}

# ── Intent patterns ─────────────────────────────────────────────────────
INTENT_PATTERNS = {
    "compare_drivers": [
        r"\bvs\b", r"\bversus\b", r"\bcompare\b", r"\bbetter\b",
        r"\bagainst\b", r"\bhead.to.head\b", r"\bmatch.?up\b",
    ],
    "telemetry": [
        r"\btelemetry\b", r"\bbraking\b", r"\bspeed\b", r"\bcorner\b",
        r"\blap.?time\b", r"\bsector\b", r"\bthrottle\b", r"\bgear\b",
        r"\btire\b", r"\btyre\b", r"\bdegradation\b",
    ],
    "driver_info": [
        r"\btell me about\b", r"\bwho is\b", r"\bstats\b", r"\bcareer\b",
        r"\bwins\b", r"\bpoles\b", r"\bprofile\b", r"\binfo\b",
    ],
    "event_location": [
        r"\bwhere\b.*(?:race|gp|grand prix|match|event)",
        r"\bvenue\b", r"\blocation\b", r"\bcircuit\b.*\bwhere\b",
    ],
    "regulations": [
        r"\brules?\b", r"\bregulations?\b", r"\bactive.?aero\b",
        r"\bx.?mode\b", r"\bz.?mode\b", r"\bboost\b", r"\bengine\b",
        r"\bpower.?unit\b", r"\bPU\b", r"\bMGU\b",
    ],
    "standings": [
        r"\bchampion\b", r"\bchampionship\b", r"\bstandings?\b",
        r"\bpoints\b", r"\btitle\b", r"\bwdc\b", r"\bwcc\b",
    ],
}

# ── Required fields per intent ──────────────────────────────────────────
REQUIRED_FIELDS = {
    "compare_drivers": ["driver_1", "driver_2"],
    "telemetry": ["driver_1", "driver_2", "track_or_gp", "session"],
    "event_location": ["date_or_event"],
}


# ═══════════════════════════════════════════════════════════════════════
#  1.  FAST LOCAL EXTRACTION  (no LLM, deterministic)
# ═══════════════════════════════════════════════════════════════════════

# Intent priority: when two intents tie or both match, prefer the more specific one.
_INTENT_PRIORITY = {
    "telemetry": 10,       # telemetry > compare_drivers
    "standings": 8,        # standings > driver_info
    "event_location": 7,
    "regulations": 6,
    "compare_drivers": 5,
    "driver_info": 3,
    "general": 0,
}


def detect_intent(prompt: str) -> str:
    """Keyword / regex-based intent detection with priority weighting."""
    lower = prompt.lower()
    scores: Dict[str, int] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, lower))
        if hits:
            scores[intent] = hits
    if not scores:
        return "general"

    # Special rule: if BOTH telemetry and compare_drivers matched,
    # telemetry is the more specific intent — always prefer it.
    if "telemetry" in scores and "compare_drivers" in scores:
        return "telemetry"

    # When multiple intents match with the same hit count, use priority
    max_hits = max(scores.values())
    tied = [k for k, v in scores.items() if v == max_hits]
    if len(tied) == 1:
        return tied[0]
    # Break ties with priority
    return max(tied, key=lambda k: _INTENT_PRIORITY.get(k, 0))


def extract_entities_local(prompt: str) -> Dict[str, Any]:
    """
    Fast, deterministic entity extraction using the alias registries.
    Returns dict with drivers, gps, sessions found.

    IMPORTANT: When two aliases resolve to the SAME driver ID, we keep
    BOTH entries so that score_confidence can detect the duplicate and
    trigger clarification.  A downstream dedup happens only AFTER
    confidence checks pass.
    """
    upper_prompt = prompt.upper()

    drivers: List[Dict[str, Any]] = []
    matched_aliases: Dict[str, List[str]] = {}  # id -> [alias, ...]

    # Match every alias that appears in the prompt (word-boundary check)
    for alias, (did, full_name) in DRIVER_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', upper_prompt):
            matched_aliases.setdefault(did, []).append(alias)

    # Build driver entries — one per ALIAS MATCH (not per unique ID)
    # so duplicates are visible to the confidence scorer.
    for did, aliases in matched_aliases.items():
        full_name = DRIVER_ALIASES[aliases[0]][1]
        if len(aliases) == 1:
            # Single alias → single entry
            drivers.append({
                "raw": aliases[0],
                "resolved": full_name,
                "id": did,
                "confidence": 0.99,
            })
        else:
            # Multiple aliases for the same ID → one entry PER alias
            for alias in aliases:
                drivers.append({
                    "raw": alias,
                    "resolved": full_name,
                    "id": did,
                    "confidence": 0.99,
                })

    # GP detection (deduplicated by resolved name)
    gps: List[Dict[str, str]] = []
    seen_gps: set = set()
    for alias, gp_name in GP_ALIASES.items():
        if alias in upper_prompt and gp_name not in seen_gps:
            gps.append({"raw": alias, "resolved": gp_name})
            seen_gps.add(gp_name)

    # Session detection (deduplicated, word-boundary)
    sessions: List[Dict[str, str]] = []
    seen_sessions: set = set()
    for alias, session_name in SESSION_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', upper_prompt) and session_name not in seen_sessions:
            sessions.append({"raw": alias, "resolved": session_name})
            seen_sessions.add(session_name)

    # Date detection
    dates: List[str] = re.findall(
        r"\b\d{1,2}[\s/\-]\w+[\s/\-]\d{2,4}\b|\b\w+\s+\d{1,2},?\s+\d{4}\b",
        prompt,
    )

    return {
        "drivers": drivers,
        "gps": gps,
        "sessions": sessions,
        "dates": dates,
    }


# ═══════════════════════════════════════════════════════════════════════
#  2.  LLM-POWERED EXTRACTION  (general common-sense)
# ═══════════════════════════════════════════════════════════════════════

EXTRACTION_SYSTEM_PROMPT = """\
You are an F1 entity-extraction engine. Given a user message, output ONLY a JSON object:
{
  "intent": "<compare_drivers|driver_info|telemetry|event_location|regulations|standings|general>",
  "drivers": [
    {"raw": "<as user wrote>", "resolved": "<full name>", "id": "<DRV_XXX>", "confidence": <0-1>}
  ],
  "gps": [
    {"raw": "<as user wrote>", "resolved": "<official GP name>"}
  ],
  "sessions": [
    {"raw": "<as user wrote>", "resolved": "<official session name>"}
  ],
  "dates": ["<any dates found>"],
  "pronouns": [
    {"raw": "<he/him/her/them/his/their>", "likely_refers_to": "<best guess from conversation context or null>"}
  ]
}

Rules:
- Resolve ALL abbreviations, nicknames, first names to their full official names.
- Use the canonical ID format DRV_XXX (e.g. DRV_HAM for Hamilton).
- If a token could refer to multiple people, set confidence lower and note alternatives.
- "LEW" and "HAM" both refer to Lewis Hamilton.
- "MAX" refers to Max Verstappen. "CHARLES" refers to Charles Leclerc.
- For GPs, resolve track nicknames (e.g. "Monza" → "Italian Grand Prix").
- For sessions, normalize (e.g. "quali" → "Qualifying").
- Only output the JSON. No explanation.
"""


def build_llm_extraction_prompt(
    user_message: str,
    conversation_entities: List[Dict[str, Any]] | None = None,
) -> str:
    """Build the user-turn content for the extraction LLM call."""
    parts = [f"User message: {user_message}"]
    if conversation_entities:
        parts.append(
            "Previously mentioned entities in this conversation: "
            + json.dumps(conversation_entities)
        )
    return "\n".join(parts)


def parse_llm_extraction(raw_content: str) -> Dict[str, Any] | None:
    """Safely parse the LLM JSON output."""
    try:
        # Strip markdown code fences if present
        cleaned = re.sub(r"```json\s*", "", raw_content)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse LLM extraction output: %s", raw_content[:200])
        return None


# ═══════════════════════════════════════════════════════════════════════
#  3.  CONFIDENCE / AMBIGUITY SCORING
# ═══════════════════════════════════════════════════════════════════════

MAX_UNVERIFIED_ASSUMPTIONS = 1


def score_confidence(
    intent: str,
    entities: Dict[str, Any],
    prompt: str,
) -> Dict[str, Any]:
    """
    Score confidence (0.0–1.0) and detect issues.

    Returns:
        {
            "confidence": float,
            "issues": [str],
            "missing_fields": [str],
            "assumptions": [str],
            "needs_clarification": bool,
        }
    """
    confidence = 1.0
    issues: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    drivers = entities.get("drivers", [])
    gps = entities.get("gps", [])
    sessions = entities.get("sessions", [])
    dates = entities.get("dates", [])
    pronouns = entities.get("pronouns", [])

    # ── Same-entity detection ───────────────────────────────────────
    if len(drivers) >= 2:
        driver_ids = [d["id"] for d in drivers]
        unique_ids = set(driver_ids)
        if len(unique_ids) < len(driver_ids):
            # Duplicates found
            from collections import Counter
            dupes = [did for did, cnt in Counter(driver_ids).items() if cnt > 1]
            for did in dupes:
                matching = [d for d in drivers if d["id"] == did]
                raw_names = [d["raw"] for d in matching]
                issues.append(
                    f'Aliases {", ".join(raw_names)} all resolve to {matching[0]["resolved"]}.'
                )
            confidence -= 0.50

    # ── Low entity confidence ───────────────────────────────────────
    for d in drivers:
        if d.get("confidence", 1.0) < 0.70:
            issues.append(
                f'Not sure who "{d["raw"]}" refers to (confidence {d["confidence"]:.0%}).'
            )
            confidence -= 0.20

    # ── Unresolved pronouns ─────────────────────────────────────────
    for p in pronouns:
        if not p.get("likely_refers_to"):
            issues.append(f'Cannot resolve pronoun "{p["raw"]}" — no prior context.')
            confidence -= 0.25
        else:
            assumptions.append(
                f'Interpreting "{p["raw"]}" as {p["likely_refers_to"]}.'
            )

    # ── Missing required fields ─────────────────────────────────────
    # Count unique driver IDs for requirement checks
    unique_driver_ids = set(d["id"] for d in drivers)
    required = REQUIRED_FIELDS.get(intent, [])
    for field in required:
        if field == "driver_1" and len(unique_driver_ids) < 1:
            missing.append("driver_1")
        elif field == "driver_2" and len(unique_driver_ids) < 2:
            missing.append("driver_2")
        elif field == "track_or_gp" and not gps:
            missing.append("track_or_gp")
        elif field == "session" and not sessions:
            missing.append("session")
        elif field == "date_or_event" and not dates and not gps:
            missing.append("date_or_event")

    if missing:
        confidence -= 0.20 * len(missing)
        issues.append(f"Missing required fields: {', '.join(missing)}.")

    # ── Vague event queries (date but no GP name) ───────────────────
    if intent == "event_location" and dates and not gps:
        issues.append("Date provided but no Grand Prix or event name specified.")
        confidence -= 0.30

    # ── Assumption budget ───────────────────────────────────────────
    if len(assumptions) > MAX_UNVERIFIED_ASSUMPTIONS:
        over = len(assumptions) - MAX_UNVERIFIED_ASSUMPTIONS
        confidence -= 0.15 * over
        issues.append(
            f"Too many assumptions ({len(assumptions)}). "
            f"Max allowed: {MAX_UNVERIFIED_ASSUMPTIONS}."
        )

    # ── Clamp ───────────────────────────────────────────────────────
    confidence = max(0.0, min(1.0, confidence))

    return {
        "confidence": round(confidence, 2),
        "issues": issues,
        "missing_fields": missing,
        "assumptions": assumptions,
        "needs_clarification": confidence < HIGH_CONFIDENCE,
    }


# ═══════════════════════════════════════════════════════════════════════
#  4.  CLARIFICATION TEMPLATE ENGINE
# ═══════════════════════════════════════════════════════════════════════

def build_clarification(
    intent: str,
    confidence: float,
    issues: List[str],
    missing_fields: List[str],
    entities: Dict[str, Any],
) -> str:
    """
    Generate a targeted, intent-specific clarification message.
    Never returns a vague 'Can you clarify?'.
    """
    drivers = entities.get("drivers", [])

    # ── Same-entity issue ───────────────────────────────────────────
    same_entity_issues = [i for i in issues if "all resolve to" in i]
    if same_entity_issues and intent == "compare_drivers":
        resolved_name = drivers[0]["resolved"] if drivers else "the same driver"
        raw_names = [d["raw"] for d in drivers]
        return (
            f'Both "{raw_names[0]}" and "{raw_names[1]}" resolve to '
            f"**{resolved_name}**. Did you mean to compare {resolved_name} "
            f"against another driver such as Norris, Leclerc, or Verstappen?"
        )

    # ── Telemetry missing fields ────────────────────────────────────
    if intent == "telemetry" and missing_fields:
        parts = ["To compare telemetry accurately, I need:"]
        if "driver_1" in missing_fields or "driver_2" in missing_fields:
            parts.append("- **Two drivers** to compare")
        if "track_or_gp" in missing_fields:
            parts.append("- **Grand Prix or circuit** (e.g. Monza, Silverstone)")
        if "session" in missing_fields:
            parts.append("- **Session** (FP1, Qualifying, Race)")
        parts.append(
            '\nExample: "Compare Hamilton vs Norris braking into Turn 1 '
            'at Monza qualifying."'
        )
        return "\n".join(parts)

    # ── Comparison missing driver ───────────────────────────────────
    if intent == "compare_drivers" and "driver_2" in missing_fields:
        d1 = drivers[0]["resolved"] if drivers else "the driver"
        return (
            f"You mentioned {d1}, but I need a **second driver** to compare against. "
            f"Who would you like to compare them with?"
        )

    # ── Event location ambiguity ────────────────────────────────────
    if intent == "event_location" and missing_fields:
        return (
            "I don't have enough context to identify the event. "
            "Please specify the **Grand Prix name**, **race series**, or "
            "**teams/drivers** involved."
        )

    # ── Very low confidence — request rephrase ──────────────────────
    if confidence < MEDIUM_CONFIDENCE:
        reason = issues[0] if issues else "The query is too ambiguous."
        return (
            f"I'm not confident I understand your question correctly. "
            f"{reason}\n\n"
            f"Could you rephrase with more specific details? For example:\n"
            f"- Name the drivers, teams, or Grand Prix\n"
            f"- Specify the session (Qualifying, Race)\n"
            f"- Clarify what information you're looking for"
        )

    # ── Generic targeted clarification (still specific) ─────────────
    if issues:
        issue_text = " ".join(issues)
        return f"I need a bit more detail: {issue_text}"

    return "Could you provide more specific details about what you'd like to know?"


# ═══════════════════════════════════════════════════════════════════════
#  5.  ENHANCED QUERY BUILDER
# ═══════════════════════════════════════════════════════════════════════

def build_enhanced_query(
    original_prompt: str,
    intent: str,
    entities: Dict[str, Any],
    confidence_result: Dict[str, Any],
) -> str:
    """
    Build an Enhanced Query (EQ) string that the agent LLM uses
    instead of the raw user prompt. Expands abbreviations, normalizes
    aliases, adds inferred intent, and preserves uncertainty.
    """
    drivers = entities.get("drivers", [])
    gps = entities.get("gps", [])
    sessions = entities.get("sessions", [])
    assumptions = confidence_result.get("assumptions", [])

    parts = [f'Original user query: "{original_prompt}"']
    parts.append(f"Detected intent: {intent}")
    parts.append(f"Confidence: {confidence_result['confidence']}")

    if drivers:
        driver_strs = []
        for d in drivers:
            driver_strs.append(f'{d["resolved"]} ({d["id"]})')
        parts.append(f"Resolved drivers: {', '.join(driver_strs)}")

    if gps:
        gp_strs = [g["resolved"] for g in gps]
        parts.append(f"Grand Prix: {', '.join(gp_strs)}")

    if sessions:
        sess_strs = [s["resolved"] for s in sessions]
        parts.append(f"Session: {', '.join(sess_strs)}")

    if assumptions:
        parts.append(f"Assumptions made: {'; '.join(assumptions)}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
#  6.  ANSWER VALIDATOR
# ═══════════════════════════════════════════════════════════════════════

VALIDATION_SYSTEM_PROMPT = """\
You are an answer-validation engine for an F1 assistant. Given:
1. The original user question
2. The extracted intent and entities
3. The proposed answer

Check this answer against a strict validation checklist and output ONLY a JSON object:
{
  "passed": true/false,
  "failures": [
    {"check": "<check name>", "reason": "<why it failed>"}
  ]
}

Validation checklist:
1. "answered_question" — Does the answer address what the user actually asked?
2. "no_unsupported_assumptions" — Does the answer avoid fabricating context that was never in the query or tools? (missing GP, made-up lap times, invented sessions)
3. "no_phantom_entities" — Does the answer avoid referencing drivers, teams, or events the user never mentioned and the tools never returned?
4. "comparison_valid" — If it's a comparison, are TWO DIFFERENT entities being compared?
5. "no_fabricated_telemetry" — Are speed, braking, lap-time values sourced from the tool output, not invented?
6. "terms_defined" — Are specialized F1 terms (X-Mode, Z-Mode, DRS, MGU-H) explained or at least not used without context?

Only report FAILED checks. If all pass, set "passed": true and "failures": [].
"""


def build_validation_prompt(
    original_prompt: str,
    intent: str,
    entities: Dict[str, Any],
    proposed_answer: str,
) -> str:
    """Build the prompt for the answer validation LLM call."""
    return (
        f"Original question: {original_prompt}\n"
        f"Intent: {intent}\n"
        f"Entities: {json.dumps(entities)}\n"
        f"Proposed answer:\n{proposed_answer}"
    )


def parse_validation_result(raw_content: str) -> Dict[str, Any]:
    """Parse the validation LLM output."""
    try:
        cleaned = re.sub(r"```json\s*", "", raw_content)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        result = json.loads(cleaned)
        return result
    except (json.JSONDecodeError, TypeError):
        logger.warning("Validation parse failed, assuming pass: %s", raw_content[:200])
        return {"passed": True, "failures": []}


# ═══════════════════════════════════════════════════════════════════════
#  7.  ORCHESTRATOR — Full analysis pipeline (called from agent node)
# ═══════════════════════════════════════════════════════════════════════

def analyze_query(
    user_prompt: str,
    conversation_entities: List[Dict[str, Any]] | None = None,
    llm_extraction: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run the full query understanding pipeline.

    Args:
        user_prompt: Raw user message.
        conversation_entities: Entities from prior conversation turns
            (for pronoun/reference resolution).
        llm_extraction: If provided, the LLM-extracted entities
            (from a preceding LLM call). If None, uses local extraction.

    Returns:
        Full analysis dict with keys:
            intent, entities, confidence, needs_clarification,
            clarification_message, enhanced_query, issues,
            missing_fields, assumptions
    """
    # 1. Intent detection (always local — fast & deterministic)
    intent = detect_intent(user_prompt)

    # 2. Entity extraction
    if llm_extraction:
        entities = llm_extraction
        # Override intent if LLM detected one
        if llm_extraction.get("intent") and llm_extraction["intent"] != "general":
            intent = llm_extraction["intent"]
    else:
        entities = extract_entities_local(user_prompt)

    # 3. Merge conversation memory for pronoun resolution
    if conversation_entities:
        pronouns = entities.get("pronouns", [])
        for p in pronouns:
            if not p.get("likely_refers_to") and conversation_entities:
                # Use most recently mentioned driver
                p["likely_refers_to"] = conversation_entities[-1].get("resolved")

    # 4. Confidence scoring
    conf = score_confidence(intent, entities, user_prompt)

    # 5. Build EQ or clarification
    clarification_msg = None
    enhanced_query = None

    if conf["confidence"] >= HIGH_CONFIDENCE:
        enhanced_query = build_enhanced_query(
            user_prompt, intent, entities, conf
        )
    else:
        clarification_msg = build_clarification(
            intent, conf["confidence"], conf["issues"],
            conf["missing_fields"], entities,
        )

    return {
        "intent": intent,
        "entities": entities,
        "confidence": conf["confidence"],
        "needs_clarification": conf["needs_clarification"],
        "clarification_message": clarification_msg,
        "enhanced_query": enhanced_query,
        "issues": conf["issues"],
        "missing_fields": conf["missing_fields"],
        "assumptions": conf["assumptions"],
    }
