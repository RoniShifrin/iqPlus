/**
 * Centralized activity-description formatter.
 *
 * Single source of truth for converting backend enum strings into
 * human-readable, language-aware labels in the Recent Activity / Updates UI.
 *
 * How it works
 * ────────────
 * 1. Pre-pass: strip full enum class-name prefixes anywhere they appear
 *    e.g.  "EnrollmentStatusEnum.ACTIVE"  → "active"
 *          "AttendanceStatusEnum.ABSENT"  → "absent"
 *    This makes the rest of the rules language-agnostic and backend-version-agnostic.
 *
 * 2. Pattern replacements (order matters):
 *    "att: absent"      → t('common.attendance') + ": " + t('att.absent')
 *    "grade 85%"        → t('common.grade') + ": 85%"
 *    "feedback added"   → t('activity.feedbackAdded')
 *    "feedback received"→ t('activity.feedbackReceived')
 *    "(active)"         → "(" + t('enrollment.active') + ")"
 *    … and all other enrollment statuses
 *
 * Translation keys used (must exist in translations.ts):
 *   common.attendance, common.grade
 *   att.present, att.absent, att.late, att.excused
 *   enrollment.active, enrollment.pending, enrollment.rejected,
 *   enrollment.inactive, enrollment.waitlisted
 *   activity.feedbackAdded, activity.feedbackReceived
 */

type TFn = (key: string) => string;

/** Maps raw enum value (lowercase) → i18n key */
const ENROLLMENT_STATUS_KEYS: Record<string, string> = {
  active:     'enrollment.active',
  pending:    'enrollment.pending',
  rejected:   'enrollment.rejected',
  inactive:   'enrollment.inactive',
  waitlisted: 'enrollment.waitlisted',
};

const ATT_STATUS_VALUES = new Set(['present', 'absent', 'late', 'excused']);

/**
 * Pre-pass: strip Python Enum class-name prefixes.
 * "SomeThingEnum.VALUE" → "value"
 * Works for any enum, so new enums added to the backend need no frontend change.
 */
function stripEnumPrefixes(text: string): string {
  return text.replace(/\b\w+Enum\.(\w+)/g, (_match, value: string) =>
    value.toLowerCase(),
  );
}

export function formatActivityDescription(
  desc: string | null | undefined,
  t: TFn,
): string {
  if (!desc) return '—';

  // Step 1 — remove full enum class-name prefixes (defensive against backend changes)
  let result = stripEnumPrefixes(desc);

  // Step 2 — "att: absent" (and any valid att status) → "Attendance: Absent"
  result = result.replace(
    /\batt:\s*(\w+)\b/gi,
    (_match, status: string) => {
      const key = status.toLowerCase();
      if (ATT_STATUS_VALUES.has(key)) {
        return `${t('common.attendance')}: ${t(`att.${key}`)}`;
      }
      return `${t('common.attendance')}: ${status}`;
    },
  );

  // Step 3 — "grade 85%" or "grade 85.0%" → "Grade: 85%"
  result = result.replace(
    /\bgrade\s+(\d+(?:\.\d+)?%?)/gi,
    (_match, val: string) => `${t('common.grade')}: ${val}`,
  );

  // Step 4 — "feedback added" / "feedback received"
  result = result.replace(/\bfeedback added\b/gi, t('activity.feedbackAdded'));
  result = result.replace(
    /\bfeedback received\b/gi,
    t('activity.feedbackReceived'),
  );

  // Step 5 — enrollment status in parentheses, e.g. "(active)" → "(Active)"
  result = result.replace(/\((\w+)\)/g, (_match, status: string) => {
    const key = ENROLLMENT_STATUS_KEYS[status.toLowerCase()];
    return key ? `(${t(key)})` : _match;
  });

  return result;
}
