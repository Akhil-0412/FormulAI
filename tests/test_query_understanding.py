"""
Tests for ParcFermé AI Query Understanding Layer.

Covers:
  - Same-entity detection (LEW vs HAM, etc.)
  - General alias resolution (common-sense, not just hardcoded)
  - Intent classification
  - Confidence scoring and threshold routing
  - Clarification template quality
  - Telemetry required-field enforcement
  - Assumption budget
  - GP and session alias resolution
  - Cross-turn pronoun resolution
"""

import pytest
from api.chatbot.query_understanding import (
    detect_intent,
    extract_entities_local,
    score_confidence,
    build_clarification,
    build_enhanced_query,
    analyze_query,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
)


# ═══════════════════════════════════════════════════════════════════════
#  INTENT DETECTION
# ═══════════════════════════════════════════════════════════════════════


class TestIntentDetection:
    def test_compare_drivers_vs(self):
        assert detect_intent("HAM vs VER") == "compare_drivers"

    def test_compare_drivers_compare(self):
        assert detect_intent("Compare Hamilton and Norris") == "compare_drivers"

    def test_compare_drivers_better(self):
        assert detect_intent("Who is better? Leclerc or Verstappen") == "compare_drivers"

    def test_telemetry_explicit(self):
        assert detect_intent("Show me telemetry for Hamilton") == "telemetry"

    def test_telemetry_braking(self):
        assert detect_intent("Braking comparison at Turn 1") == "telemetry"

    def test_telemetry_speed(self):
        assert detect_intent("Top speed analysis") == "telemetry"

    def test_driver_info(self):
        assert detect_intent("Tell me about Leclerc") == "driver_info"

    def test_driver_info_stats(self):
        assert detect_intent("What are Hamilton's career stats?") == "driver_info"

    def test_event_location(self):
        assert detect_intent("Where is the race this weekend?") == "event_location"

    def test_regulations(self):
        assert detect_intent("Explain the 2026 regulations") == "regulations"

    def test_regulations_active_aero(self):
        assert detect_intent("What is active aero?") == "regulations"

    def test_standings(self):
        assert detect_intent("Who is the current champion?") == "standings"

    def test_general_fallback(self):
        assert detect_intent("Hello, how are you?") == "general"


# ═══════════════════════════════════════════════════════════════════════
#  LOCAL ENTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════


class TestEntityExtraction:
    def test_single_driver_code(self):
        result = extract_entities_local("Tell me about HAM")
        drivers = result["drivers"]
        assert len(drivers) == 1
        assert drivers[0]["id"] == "DRV_HAM"
        assert drivers[0]["resolved"] == "Lewis Hamilton"

    def test_single_driver_name(self):
        result = extract_entities_local("Tell me about Hamilton")
        drivers = result["drivers"]
        assert len(drivers) == 1
        assert drivers[0]["id"] == "DRV_HAM"

    def test_two_different_drivers(self):
        result = extract_entities_local("HAM vs VER")
        drivers = result["drivers"]
        ids = {d["id"] for d in drivers}
        assert "DRV_HAM" in ids
        assert "DRV_VER" in ids

    def test_same_driver_different_aliases(self):
        """LEW vs HAM — both resolve to Hamilton, kept as 2 entries for duplicate detection."""
        result = extract_entities_local("LEW vs HAM")
        drivers = result["drivers"]
        # Both aliases produce separate entries so confidence scorer catches dups
        assert len(drivers) == 2
        assert all(d["id"] == "DRV_HAM" for d in drivers)

    def test_nickname_resolution(self):
        """CHECO → Sergio Pérez."""
        result = extract_entities_local("How is CHECO doing?")
        drivers = result["drivers"]
        assert len(drivers) == 1
        assert drivers[0]["id"] == "DRV_PER"

    def test_first_name_resolution(self):
        """CHARLES → Charles Leclerc."""
        result = extract_entities_local("What about Charles?")
        drivers = result["drivers"]
        assert len(drivers) == 1
        assert drivers[0]["id"] == "DRV_LEC"

    def test_gp_alias(self):
        result = extract_entities_local("Race at Monza this year")
        gps = result["gps"]
        assert len(gps) >= 1
        assert gps[0]["resolved"] == "Italian Grand Prix"

    def test_session_alias(self):
        result = extract_entities_local("qualifying results")
        sessions = result["sessions"]
        assert any(s["resolved"] == "Qualifying" for s in sessions)

    def test_multiple_gp_keywords(self):
        result = extract_entities_local("Compare Silverstone and Monza")
        gps = result["gps"]
        resolved = {g["resolved"] for g in gps}
        assert "British Grand Prix" in resolved
        assert "Italian Grand Prix" in resolved

    def test_historical_driver(self):
        result = extract_entities_local("Senna vs Prost")
        drivers = result["drivers"]
        ids = {d["id"] for d in drivers}
        assert "DRV_SEN" in ids
        assert "DRV_PRO" in ids


# ═══════════════════════════════════════════════════════════════════════
#  SAME-ENTITY DETECTION (the core failure the user reported)
# ═══════════════════════════════════════════════════════════════════════


class TestSameEntityDetection:
    def test_lew_vs_ham(self):
        """The flagship regression test from the user spec."""
        analysis = analyze_query("LEW vs HAM")
        assert analysis["needs_clarification"] is True
        assert analysis["confidence"] < HIGH_CONFIDENCE
        assert any("resolve to" in i.lower() or "same" in i.lower()
                    for i in analysis["issues"])

    def test_lewis_vs_hamilton(self):
        """Full name vs surname — same person."""
        analysis = analyze_query("LEWIS vs HAMILTON")
        assert analysis["needs_clarification"] is True

    def test_max_vs_verstappen(self):
        """First name vs surname — same person."""
        analysis = analyze_query("MAX vs VERSTAPPEN")
        assert analysis["needs_clarification"] is True

    def test_charles_vs_leclerc(self):
        analysis = analyze_query("CHARLES vs LECLERC")
        assert analysis["needs_clarification"] is True

    def test_checo_vs_perez(self):
        analysis = analyze_query("CHECO vs PEREZ")
        assert analysis["needs_clarification"] is True

    def test_different_drivers_proceed(self):
        """HAM vs VER should NOT trigger clarification."""
        analysis = analyze_query("HAM vs VER")
        assert analysis["confidence"] >= HIGH_CONFIDENCE
        assert analysis["needs_clarification"] is False


# ═══════════════════════════════════════════════════════════════════════
#  CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceScoring:
    def test_high_confidence_simple_query(self):
        """Simple driver info query → high confidence."""
        analysis = analyze_query("Tell me about Leclerc")
        assert analysis["confidence"] >= HIGH_CONFIDENCE

    def test_high_confidence_full_telemetry(self):
        """Fully specified telemetry query."""
        analysis = analyze_query(
            "Compare Hamilton vs Norris braking into Turn 1 at Monza qualifying"
        )
        assert analysis["confidence"] >= HIGH_CONFIDENCE

    def test_medium_confidence_missing_fields(self):
        """Telemetry with no GP/session → medium (clarification)."""
        analysis = analyze_query("Compare telemetry Hamilton vs Norris")
        assert MEDIUM_CONFIDENCE <= analysis["confidence"] < HIGH_CONFIDENCE
        assert analysis["needs_clarification"] is True
        assert "track_or_gp" in analysis["missing_fields"] or "session" in analysis["missing_fields"]

    def test_low_confidence_vague(self):
        """Very vague query → low confidence."""
        analysis = analyze_query("Where is the May 2, 2026 match going to happen?")
        assert analysis["confidence"] < HIGH_CONFIDENCE
        # The word "match" is ambiguous — could be any sport

    def test_bare_compare_telemetry(self):
        """'Compare telemetry' with no drivers → low."""
        analysis = analyze_query("Compare telemetry")
        assert analysis["needs_clarification"] is True

    def test_regulations_high_confidence(self):
        """Regulation questions are self-contained."""
        analysis = analyze_query("What are the 2026 F1 regulations?")
        assert analysis["confidence"] >= HIGH_CONFIDENCE

    def test_standings_high_confidence(self):
        analysis = analyze_query("Who won the 2025 championship?")
        assert analysis["confidence"] >= HIGH_CONFIDENCE


# ═══════════════════════════════════════════════════════════════════════
#  CLARIFICATION QUALITY
# ═══════════════════════════════════════════════════════════════════════


class TestClarificationQuality:
    def test_same_entity_clarification_is_specific(self):
        analysis = analyze_query("LEW vs HAM")
        msg = analysis["clarification_message"]
        assert msg is not None
        # Must mention Hamilton by name
        assert "Hamilton" in msg
        # Must NOT be the vague "Can you clarify?"
        assert msg != "Can you clarify?"
        assert "clarify" not in msg.lower() or "rephrase" not in msg.lower()

    def test_telemetry_clarification_lists_requirements(self):
        analysis = analyze_query("Compare telemetry Hamilton vs Norris")
        msg = analysis["clarification_message"]
        assert msg is not None
        # Should mention GP/circuit AND session
        assert "Grand Prix" in msg or "circuit" in msg
        assert "session" in msg.lower() or "Session" in msg

    def test_missing_driver2_clarification(self):
        analysis = analyze_query("Compare Hamilton")
        msg = analysis["clarification_message"]
        assert msg is not None
        assert "second driver" in msg.lower() or "compare" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════
#  ENHANCED QUERY
# ═══════════════════════════════════════════════════════════════════════


class TestEnhancedQuery:
    def test_eq_contains_resolved_names(self):
        analysis = analyze_query("Tell me about LEC")
        eq = analysis.get("enhanced_query")
        assert eq is not None
        assert "Charles Leclerc" in eq
        assert "DRV_LEC" in eq

    def test_eq_contains_intent(self):
        analysis = analyze_query("Who won the championship?")
        eq = analysis.get("enhanced_query")
        assert eq is not None
        assert "standings" in eq.lower()

    def test_eq_not_generated_for_low_confidence(self):
        """If confidence < threshold, no EQ — clarification instead."""
        analysis = analyze_query("LEW vs HAM")
        assert analysis.get("enhanced_query") is None
        assert analysis.get("clarification_message") is not None


# ═══════════════════════════════════════════════════════════════════════
#  CROSS-TURN MEMORY
# ═══════════════════════════════════════════════════════════════════════


class TestCrossTurnMemory:
    def test_pronoun_resolution_with_context(self):
        """If prior entities exist, pronouns should try to resolve."""
        prior = [{"raw": "HAM", "resolved": "Lewis Hamilton", "id": "DRV_HAM"}]

        # Simulate LLM extraction that found a pronoun
        llm_result = {
            "intent": "compare_drivers",
            "drivers": [
                {"raw": "Norris", "resolved": "Lando Norris", "id": "DRV_NOR", "confidence": 0.95},
            ],
            "gps": [],
            "sessions": [],
            "dates": [],
            "pronouns": [
                {"raw": "him", "likely_refers_to": None},
            ],
        }

        analysis = analyze_query(
            "Compare him with Norris",
            conversation_entities=prior,
            llm_extraction=llm_result,
        )

        # The pronoun should now resolve to Hamilton
        pronouns = analysis["entities"].get("pronouns", [])
        if pronouns:
            assert pronouns[0].get("likely_refers_to") == "Lewis Hamilton"


# ═══════════════════════════════════════════════════════════════════════
#  END-TO-END SPEC EXAMPLES
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEndExamples:
    """Tests directly from the user's specification document."""

    def test_lew_vs_ham_requires_clarification(self):
        analysis = analyze_query("LEW vs HAM")
        assert analysis["needs_clarification"] is True
        assert "Hamilton" in analysis["clarification_message"]

    def test_tell_me_about_leclerc_proceeds(self):
        analysis = analyze_query("Tell me about Leclerc")
        assert analysis["confidence"] >= HIGH_CONFIDENCE
        assert analysis["needs_clarification"] is False
        assert analysis["enhanced_query"] is not None

    def test_may_2_2026_match_low_confidence(self):
        analysis = analyze_query("Where is the May 2, 2026 match going to happen?")
        assert analysis["needs_clarification"] is True

    def test_full_telemetry_query_proceeds(self):
        analysis = analyze_query(
            "Compare Hamilton vs Norris braking into Turn 1 at Monza qualifying"
        )
        assert analysis["confidence"] >= HIGH_CONFIDENCE
        assert analysis["needs_clarification"] is False

    def test_bare_compare_telemetry_needs_clarification(self):
        analysis = analyze_query("Compare telemetry")
        assert analysis["needs_clarification"] is True
        assert len(analysis["missing_fields"]) > 0
