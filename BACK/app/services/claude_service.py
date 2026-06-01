"""Claude AI service for student progress analysis.

Only academic indicators are passed — no student PII.
"""
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


async def analyze_student_progress(
    grades: list[float],
    attendance_rate: float,
    trend: str,
    lesson_count: int,
    language: str = "en",
) -> dict:
    """
    Analyze academic indicators using Claude AI (or rule-based fallback).

    Input contains only academic data — no student identity.

    Returns:
        {
            "alert_level": "info" | "warning" | "critical",
            "explanation": str,
            "recommended_action": str
        }
    """
    if ANTHROPIC_API_KEY:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
            prompt = _build_prompt(grades, attendance_rate, trend, lesson_count, language)
            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
                timeout=15.0,
            )
            text = message.content[0].text.strip()
            result = _parse_response(text)
            logger.info("Claude AI analysis completed, level=%s", result["alert_level"])
            return result
        except Exception as exc:
            logger.warning("Claude analysis failed (%s), using rule-based fallback", exc)

    return _fallback(grades, attendance_rate, trend, language)


# ── helpers ──────────────────────────────────────────────────────────────────

def _build_prompt(
    grades: list, attendance_rate: float, trend: str, lesson_count: int,
    language: str = "en",
) -> str:
    grade_str = ", ".join(f"{g:.1f}" for g in grades[-10:]) if grades else "none"
    lang_instruction = (
        "Respond in Hebrew. All explanation and recommended_action values must be in Hebrew."
        if language == "he"
        else "Respond in English."
    )
    return (
        "You are an academic monitoring AI. Analyze these student indicators and "
        "return ONLY valid JSON — no explanation outside the JSON.\n\n"
        f"{lang_instruction}\n\n"
        f"Recent grades (latest first): {grade_str}\n"
        f"Attendance rate: {attendance_rate:.1f}%\n"
        f"Grade trend: {trend}\n"
        f"Lessons recorded: {lesson_count}\n\n"
        "Detect: grade drop >15%, attendance <75%, stagnation (below 60 for 3+ lessons).\n\n"
        'Return exactly: {"alert_level": "info|warning|critical", '
        '"explanation": "...", "recommended_action": "..."}'
    )


def _parse_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if all(k in data for k in ("alert_level", "explanation", "recommended_action")):
                if data["alert_level"] not in ("info", "warning", "critical"):
                    data["alert_level"] = "info"
                return data
        except json.JSONDecodeError:
            pass
    return {
        "alert_level": "info",
        "explanation": text[:300],
        "recommended_action": "Review student progress.",
    }


def _fallback(grades: list, attendance_rate: float, trend: str, language: str = "en") -> dict:
    """Rule-based fallback when Claude is unavailable."""
    from app.services.ai_messages import msg, trend_label
    avg = sum(grades) / len(grades) if grades else 0.0

    if attendance_rate < 75 and avg < 60:
        return {
            "alert_level": "critical",
            "explanation": msg("cl.critical.explanation", language, att=attendance_rate, avg=avg),
            "recommended_action": msg("cl.critical.action", language),
        }

    if trend == "declining" and avg < 65:
        return {
            "alert_level": "warning",
            "explanation": msg("cl.declining.explanation", language, avg=avg),
            "recommended_action": msg("cl.declining.action", language),
        }

    if attendance_rate < 75:
        return {
            "alert_level": "warning",
            "explanation": msg("cl.attendance.explanation", language, att=attendance_rate),
            "recommended_action": msg("cl.attendance.action", language),
        }

    if len(grades) >= 3 and all(g < 60 for g in grades[-3:]):
        return {
            "alert_level": "warning",
            "explanation": msg("cl.stagnation.explanation", language, n=min(3, len(grades))),
            "recommended_action": msg("cl.stagnation.action", language),
        }

    return {
        "alert_level": "info",
        "explanation": msg(
            "cl.info.explanation", language,
            trend=trend_label(trend, language), avg=avg, att=attendance_rate,
        ),
        "recommended_action": msg("cl.info.action", language),
    }
