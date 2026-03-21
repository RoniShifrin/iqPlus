"""Feedback Text Analysis Service.

Analyses teacher feedback text to extract academic indicators and a sentiment
score.  The result is stored as a FeedbackAnalysis document — a derived layer
that never overwrites the original Feedback record.

The score engine reads FeedbackAnalysis.calculated_contribution in preference
to the raw SentimentEnum when analyses are available.

Design
------
* Rule-based keyword matching — works offline, no API key required.
* Each keyword maps to (academic_tag, strength_score 0-100).
* Positive / negative signal banks are evaluated independently.
* calculated_contribution = blend(enum_base, text_score) where text score
  carries 60 % weight once enough signals are found.
* confidence rises with the number of matched indicators (saturates at 1.0
  after 4+ matches).

Can be swapped for a Claude-powered analysis by replacing `_analyze_text()`
with an async call to the Anthropic API while keeping the same output shape.
"""
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword banks  →  (academic_tag, strength_score)
# Strength scores are calibrated so that:
#   strong positive ≈ 85-100, moderate positive ≈ 65-84
#   strong negative ≈  0-20,  moderate negative ≈ 21-40
# ---------------------------------------------------------------------------

_POSITIVE: dict[str, tuple[str, float]] = {
    "excellent":             ("effort",        95.0),
    "outstanding":           ("effort",        95.0),
    "exceptional":           ("effort",        95.0),
    "superb":                ("effort",        92.0),
    "great":                 ("effort",        85.0),
    "good":                  ("effort",        75.0),
    "improved":              ("improvement",   90.0),
    "improving":             ("improvement",   88.0),
    "improvement":           ("improvement",   85.0),
    "progress":              ("improvement",   80.0),
    "progressing":           ("improvement",   78.0),
    "growing":               ("improvement",   75.0),
    "participating":         ("participation", 80.0),
    "participates":          ("participation", 78.0),
    "active":                ("participation", 72.0),
    "raises hand":           ("participation", 82.0),
    "contributes":           ("participation", 75.0),
    "engaged":               ("engagement",    82.0),
    "engaging":              ("engagement",    78.0),
    "attentive":             ("engagement",    80.0),
    "focused":               ("engagement",    78.0),
    "enthusiastic":          ("engagement",    85.0),
    "motivated":             ("engagement",    83.0),
    "consistent":            ("consistency",   80.0),
    "consistently":          ("consistency",   80.0),
    "reliable":              ("consistency",   78.0),
    "on time":               ("consistency",   75.0),
    "punctual":              ("consistency",   78.0),
    "hardworking":           ("effort",        88.0),
    "diligent":              ("effort",        88.0),
    "dedicated":             ("effort",        85.0),
    "submitted":             ("homework",      72.0),
    "submits":               ("homework",      72.0),
    "completes":             ("homework",      70.0),
    "homework submitted":    ("homework",      82.0),
    "assignments complete":  ("homework",      82.0),
    "understands":           ("understanding", 80.0),
    "grasps":                ("understanding", 80.0),
    "mastered":              ("understanding", 92.0),
    "comprehends":           ("understanding", 78.0),
    "well-behaved":          ("behavior",      82.0),
    "respectful":            ("behavior",      80.0),
    "cooperative":           ("behavior",      80.0),
    "positive attitude":     ("behavior",      85.0),
    "kind":                  ("behavior",      75.0),
}

_NEGATIVE: dict[str, tuple[str, float]] = {
    "struggling":            ("understanding", 20.0),
    "struggles":             ("understanding", 22.0),
    "difficulty":            ("understanding", 28.0),
    "difficult":             ("understanding", 30.0),
    "poor":                  ("effort",        18.0),
    "failing":               ("understanding", 10.0),
    "failed":                ("understanding", 12.0),
    "missing":               ("homework",      15.0),
    "incomplete":            ("homework",      22.0),
    "not submitted":         ("homework",      12.0),
    "late submission":       ("consistency",   25.0),
    "late":                  ("consistency",   28.0),
    "absent":                ("behavior",      18.0),
    "frequently absent":     ("behavior",      10.0),
    "disengaged":            ("engagement",    12.0),
    "distracted":            ("engagement",    18.0),
    "unfocused":             ("engagement",    18.0),
    "inattentive":           ("engagement",    16.0),
    "disruptive":            ("behavior",      10.0),
    "disrespectful":         ("behavior",      8.0),
    "not participating":     ("participation", 15.0),
    "doesn't participate":   ("participation", 15.0),
    "passive":               ("participation", 25.0),
    "lacks":                 ("effort",        22.0),
    "lack of effort":        ("effort",        12.0),
    "no effort":             ("effort",        8.0),
    "needs improvement":     ("improvement",   25.0),
    "needs help":            ("understanding", 28.0),
    "doesn't understand":    ("understanding", 12.0),
    "does not understand":   ("understanding", 12.0),
    "cannot understand":     ("understanding", 10.0),
    "concerns":              ("behavior",      28.0),
    "concerning":            ("behavior",      25.0),
    "worried":               ("behavior",      28.0),
    "inconsistent":          ("consistency",   22.0),
}

# Sentiment enum → base score (fallback when no text signals found)
_ENUM_BASE: dict[str, float] = {
    "positive": 80.0,
    "neutral":  50.0,
    "negative": 20.0,
}


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------

def _analyze_text(text: str, sentiment_enum: str) -> dict:
    """
    Returns a dict with:
        sentiment_label, sentiment_score, extracted_tags,
        confidence, calculated_contribution
    """
    normalized = text.lower()
    # Collapse whitespace so multi-word phrases are found
    normalized = re.sub(r"\s+", " ", normalized)

    positive_hits: list[tuple[str, float]] = []
    negative_hits: list[tuple[str, float]] = []

    for phrase, (tag, strength) in _POSITIVE.items():
        if phrase in normalized:
            positive_hits.append((tag, strength))

    for phrase, (tag, strength) in _NEGATIVE.items():
        if phrase in normalized:
            negative_hits.append((tag, strength))

    # Deduplicate tags (keep highest-strength hit per tag)
    tag_scores: dict[str, float] = {}
    polarity: float = 0.0   # accumulated signed signal

    for tag, strength in positive_hits:
        tag_scores[tag] = max(tag_scores.get(tag, 0.0), strength)
        polarity += strength

    for tag, strength in negative_hits:
        tag_scores[tag] = max(tag_scores.get(tag, 0.0), 100.0 - strength)
        polarity -= strength

    extracted_tags = sorted(tag_scores.keys())
    total_hits = len(positive_hits) + len(negative_hits)

    # Confidence: saturates at 1.0 after 4+ matched indicators
    confidence = round(min(1.0, total_hits / 4.0), 2)

    # Text-derived sentiment score
    if total_hits > 0:
        net_score = (polarity / total_hits) + 50.0   # centre around 50
        text_score = round(min(max(net_score, 0.0), 100.0), 2)
    else:
        text_score = None  # no text signals found

    # Enum base
    enum_base = _ENUM_BASE.get(sentiment_enum, 50.0)

    # Blend: text analysis carries 60 % when confidence is high
    if text_score is not None:
        blend_weight = 0.4 + 0.2 * confidence   # 40–60 % text contribution
        contribution = round(
            (1 - blend_weight) * enum_base + blend_weight * text_score,
            2,
        )
        sentiment_score = round(
            0.5 * enum_base + 0.5 * text_score, 2
        )
    else:
        contribution = enum_base
        sentiment_score = enum_base
        confidence = max(confidence, 0.1)   # at least low confidence

    # Derive sentiment label from final score
    if sentiment_score >= 65.0:
        sentiment_label = "positive"
    elif sentiment_score >= 40.0:
        sentiment_label = "neutral"
    else:
        sentiment_label = "negative"

    return {
        "sentiment_label":        sentiment_label,
        "sentiment_score":        sentiment_score,
        "extracted_tags":         extracted_tags,
        "confidence":             confidence,
        "calculated_contribution": contribution,
    }


# ---------------------------------------------------------------------------
# Service entry point
# ---------------------------------------------------------------------------

class FeedbackAnalysisService:
    """Async entry points called from the academic route."""

    @staticmethod
    async def analyze_and_save(feedback) -> Optional[object]:
        """
        Analyse *feedback* (a Feedback document) and persist a FeedbackAnalysis.
        Returns the saved FeedbackAnalysis or None on error.
        """
        try:
            from app.models import FeedbackAnalysis
            from app.repositories import FeedbackAnalysisRepository

            sentiment_val = (
                feedback.sentiment.value
                if hasattr(feedback.sentiment, "value")
                else str(feedback.sentiment)
            )

            result = _analyze_text(feedback.content or "", sentiment_val)

            fa = await FeedbackAnalysisRepository.create(
                feedback_id=str(feedback.id),
                student_id=feedback.student_id,
                course_id=feedback.course_id,
                original_feedback_text=feedback.content or "",
                **result,
            )
            logger.info(
                "FeedbackAnalysis saved feedback=%s student=%s contribution=%.1f tags=%s",
                str(feedback.id), feedback.student_id,
                result["calculated_contribution"], result["extracted_tags"],
            )

            # Create a GradeSuggestion for the teacher to review — only when
            # the analysis finds a meaningful signal (deviation > 10 from neutral 50)
            contribution = result["calculated_contribution"]
            if abs(contribution - 50.0) > 10.0:
                try:
                    from app.repositories import GradeSuggestionRepository
                    tags = result.get("extracted_tags", [])
                    tag_str = ", ".join(tags) if tags else "general feedback"
                    direction = "positive" if contribution > 50 else "negative"
                    reason = (
                        f"AI analysis of feedback detected {direction} signals "
                        f"({tag_str}). Suggested contribution: {contribution:.0f}/100."
                    )
                    await GradeSuggestionRepository.create(
                        student_id=feedback.student_id,
                        course_id=feedback.course_id,
                        feedback_id=str(feedback.id),
                        suggested_score=round(contribution, 1),
                        reason=reason,
                    )
                    logger.info(
                        "GradeSuggestion created student=%s course=%s score=%.1f",
                        feedback.student_id, feedback.course_id, contribution,
                    )
                except Exception as gs_exc:
                    logger.warning("GradeSuggestion creation skipped: %s", gs_exc)

            return fa
        except Exception as exc:
            logger.error("FeedbackAnalysisService.analyze_and_save failed: %s", exc)
            return None

    @staticmethod
    def build_human_summary(analyses: list) -> str:
        """
        Convert recent FeedbackAnalysis documents into a single readable sentence
        suitable for display to students / parents.
        """
        if not analyses:
            return ""

        recent = sorted(analyses, key=lambda a: a.created_at, reverse=True)[:5]
        dominant = recent[0].sentiment_label

        # Aggregate tag frequency
        tag_counts: dict[str, int] = {}
        for a in recent:
            for t in a.extracted_tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])[:2]]
        tag_str = " and ".join(t.replace("_", " ") for t in top_tags) if top_tags else ""

        if dominant == "positive":
            if tag_str:
                return f"Recent teacher feedback highlights strong {tag_str}."
            return "Recent teacher feedback is generally positive."
        if dominant == "negative":
            if tag_str:
                return f"Recent teacher feedback indicates concerns around {tag_str}."
            return "Recent teacher feedback indicates areas needing improvement."
        if tag_str:
            return f"Recent teacher feedback notes average {tag_str}."
        return "Recent teacher feedback is neutral."
