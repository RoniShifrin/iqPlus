"""Bilingual (en / he) message templates for all AI-generated text.

Usage:
    from app.services.ai_messages import msg
    text = msg("key", lang, var=value)

Only text values change per language — JSON field names stay the same.
"""

_T: dict = {
    "en": {
        # ── Feedback analysis summary ─────────────────────────────────
        "fb.positive_with_tags":    "Recent teacher feedback highlights strong {tag_str}.",
        "fb.positive_no_tags":      "Recent teacher feedback is generally positive.",
        "fb.negative_with_tags":    "Recent teacher feedback indicates concerns around {tag_str}.",
        "fb.negative_no_tags":      "Recent teacher feedback indicates areas needing improvement.",
        "fb.neutral_with_tags":     "Recent teacher feedback notes average {tag_str}.",
        "fb.neutral_no_tags":       "Recent teacher feedback is neutral.",

        # ── Feedback trend ────────────────────────────────────────────
        "fbt.no_data":              "No feedback data available for this period.",
        "fbt.neg_over_half":        "Over half of recent feedback ({neg_pct}%) is negative.",
        "fbt.neg_moderate":         "{neg_pct}% of recent feedback is negative — monitor closely.",
        "fbt.pos_majority":         "Predominantly positive feedback ({pos_pct}%).",
        "fbt.mixed":                "Feedback sentiment is mixed.",
        "fbt.recurring_areas":      "Recurring areas: {areas}.",
        "fbt.trend_worsening":      "Trend is worsening compared to the previous period.",
        "fbt.trend_improving":      "Trend is improving compared to the previous period.",

        # ── Teacher assistant ─────────────────────────────────────────
        "ta.no_students":           "No active students enrolled in this course.",
        "ta.class_avg":             "Class average: {avg}/100.",
        "ta.excellent_count":       "{n} student(s) performing excellently.",
        "ta.high_risk_count":       "{n} student(s) at high risk — immediate attention recommended.",
        "ta.medium_risk_count":     "{n} student(s) at medium risk — monitor closely.",
        "ta.recent_alerts":         "{n} AI alert(s) raised in the past 14 days.",
        "ta.all_normal":            "All students appear to be progressing normally.",
        "ta.declining_trend":       "Declining trend detected for: {names}{suffix}.",
        "ta.improving_count":       "{n} student(s) show an improving trend.",
        "ta.group_review":          "More than 30% of the class needs attention — consider a group review session.",
        "ta.recent_alert":          "Recent alert: {message}",

        # ── Student insights panel ────────────────────────────────────
        "si.high_risk_courses":     "At high risk in {n} course(s) — teacher attention recommended.",
        "si.improving_courses":     "Improvement trend detected in {n} course(s).",
        "si.declining_courses":     "Declining performance noted in {n} course(s).",
        "si.feedback_concerns":     "Recent feedback indicates concerns in: {tag_str}.",
        "si.feedback_positive":     "Positive feedback highlights: {tag_str}.",
        "si.perf_below_threshold":  "Performance below threshold in {n} course(s).",
        "si.strong_avg":            "Strong overall performance with an average of {avg}/100.",

        # ── Dashboard insights — teacher ──────────────────────────────
        "di.teacher.no_courses":    "No active courses yet. Create a course to start tracking student progress.",
        "di.teacher.high_risk":     "{n} student(s) across your courses are at high risk — consider scheduling a check-in.",
        "di.teacher.needs_attn":    "{n} student(s) need attention based on recent performance data.",
        "di.teacher.improving":     "{n} student(s) are showing an improving trend — positive momentum worth acknowledging.",
        "di.teacher.best_course":   "Your strongest course right now is {course} (avg score {avg}/100).",
        "di.teacher.pos_feedback":  "Recent feedback trend across your courses is mostly positive.",
        "di.teacher.neg_feedback":  "Recent feedback shows more negative sentiment — a group review session may help.",
        "di.teacher.all_normal":    "All students appear to be progressing normally. Keep up the great work!",

        # ── Dashboard insights — student ──────────────────────────────
        "di.student.avg_excellent": "Your average performance across all courses is {avg}/100 — excellent work!",
        "di.student.avg_solid":     "Your average performance score is {avg}/100 — solid progress with room to grow.",
        "di.student.avg_low":       "Your average performance score is {avg}/100 — focused effort on core concepts can improve this significantly.",
        "di.student.high_risk":     "You are at high risk in {n} course(s) — reaching out to your teacher for support is recommended.",
        "di.student.improving":     "Improving performance detected in {n} course(s) — keep it up!",
        "di.student.declining":     "Performance is declining in {n} course(s) — review the material and seek help early.",
        "di.student.no_data":       "Your academic data is being tracked. Consistent attendance and coursework will build a complete progress picture.",

        # ── Dashboard insights — parent ───────────────────────────────
        "di.parent.no_children":    "No linked children found. Contact your school administrator to link your account.",
        "di.parent.child_high_risk":"{child} is at high risk in {n} course(s) — please contact their teacher.",
        "di.parent.child_improving":"{child} shows an improving trend in {n} course(s).",
        "di.parent.child_alert":    "{child}: {message}",
        "di.parent.all_stable":     "No recent alerts or significant changes detected. Everything appears stable for your children.",

        # ── Dashboard insights — admin ────────────────────────────────
        "di.admin.high_risk":       "{n} student(s) are at high academic risk across the platform.",
        "di.admin.alerts":          "{n} AI alert(s) generated in the past 7 days.",
        "di.admin.active_courses":  "{n} active course(s) currently running across the platform.",
        "di.admin.at_risk_enroll":  "{n} enrollment(s) show a declining trend — consider a system-wide intervention review.",
        "di.admin.improving_enroll":"{n} enrollment(s) showing improvement — the platform is having a positive academic impact.",
        "di.admin.stable":          "System performance looks stable. No urgent patterns detected.",

        # ── Admin AI overview ─────────────────────────────────────────
        "ao.high_risk":             "{n} enrollment(s) at high risk ({pct}% of tracked).",
        "ao.declining_courses":     "{n} course(s) show declining performance trends.",
        "ao.teacher_overload":      "{n} teacher(s) managing 3+ active courses.",
        "ao.stable":                "System performance looks stable. No urgent patterns detected.",

        # ── Feedback suggestion — score + classification ──────────────
        "fs.score.excellent.encouraging":   "Excellent work! Your current score of {val}/100 reflects outstanding dedication and consistent performance.",
        "fs.score.excellent.formal":        "Your academic performance is at an excellent level, with a composite score of {val}/100.",
        "fs.score.excellent.constructive":  "Your overall score of {val}/100 places you in the excellent category — a strong result.",
        "fs.score.good.encouraging":        "You're doing well with a score of {val}/100 — keep building on this strong foundation!",
        "fs.score.good.formal":             "Your current performance score of {val}/100 demonstrates steady and good progress.",
        "fs.score.good.constructive":       "Your score of {val}/100 reflects solid progress, with clear room for further improvement.",
        "fs.score.average.encouraging":     "You're making real progress with a score of {val}/100. With focused effort, I know you can reach the next level.",
        "fs.score.average.formal":          "Your current performance score is {val}/100, which is at an average level.",
        "fs.score.average.constructive":    "Your score of {val}/100 indicates average performance. Strengthening your study habits could lead to significant improvement.",
        "fs.score.needs_attention.encouraging": "I want to reach out because your current score of {val}/100 suggests you're facing some challenges — and I believe you can turn this around.",
        "fs.score.needs_attention.formal":      "Your current performance score of {val}/100 requires immediate attention.",
        "fs.score.needs_attention.constructive":"Your score of {val}/100 indicates this course needs more focus and consistent effort right now.",

        # ── Feedback suggestion — attendance ──────────────────────────
        "fs.att.low.encouraging":   "Your attendance has been lower than expected — regular presence makes a significant difference to your overall progress.",
        "fs.att.low.formal":        "Attendance is a concern (attendance component: {att}/100). Please prioritize consistent class participation.",
        "fs.att.low.constructive":  "Attendance needs improvement — please make class participation a consistent priority.",
        "fs.att.high":              "Your consistent attendance is commendable and positively impacts your overall performance.",
        "fs.att.grades_low":        "Despite reasonable attendance, grades could be strengthened through additional practice and review of course materials.",

        # ── Feedback suggestion — prediction ──────────────────────────
        "fs.pred.improving.encouraging": "I can see a clear upward trend in your performance — keep this momentum going!",
        "fs.pred.improving.other":       "Your performance trajectory is on an improving trend. Maintaining this consistency will lead to great results.",
        "fs.pred.at_risk.encouraging":   "I'd really like to see you bounce back — please don't hesitate to reach out for extra support.",
        "fs.pred.at_risk.formal":        "Based on current data, your progress trajectory requires intervention. Please schedule a meeting to discuss academic support options.",
        "fs.pred.at_risk.constructive":  "There is a declining performance trend that needs to be addressed. Reviewing core concepts and seeking additional help is strongly recommended.",

        # ── Feedback suggestion — feedback history ────────────────────
        "fs.fb.neg.encouraging":    "Previous feedback has highlighted areas such as {area_str} — small targeted improvements here can make a big difference.",
        "fs.fb.neg.other":          "Areas requiring focused attention based on prior feedback: {areas}.",
        "fs.fb.pos":                "Positive feedback highlights strengths in: {areas}.",

        # ── Feedback suggestion — alerts ──────────────────────────────
        "fs.alert.attendance.encouraging": "I noticed an attendance alert — making class a consistent priority will help you stay on track.",
        "fs.alert.feedback.encouraging":   "Remember: challenges are a natural part of learning, and asking for help is always the right move.",

        # ── Feedback suggestion — closings ────────────────────────────
        "fs.closing.encouraging":   "Keep up the effort — I'm here to support you every step of the way!",
        "fs.closing.formal":        "Please do not hesitate to contact me should you require any academic assistance.",
        "fs.closing.constructive":  "If you have questions or need additional support, please reach out during office hours or via the course chat.",

        # ── Feedback suggestion — empty fallbacks ─────────────────────
        "fs.empty.encouraging":     "Keep up the good work! Consistent effort and regular class participation are key to success. Don't hesitate to ask questions when you need support.",
        "fs.empty.formal":          "This is to acknowledge your participation in this course. Please ensure consistent engagement with all coursework and contact me if you require academic support.",
        "fs.empty.constructive":    "Please ensure consistent attendance and active engagement with the course material. Reach out if you need support or have questions about the content.",

        # ── Planner — workload analysis ───────────────────────────────
        "pl.wl.adds_hours":         "This plan adds {h:.1f} weekly hours across {days} day(s).",
        "pl.wl.overloaded_one":     "Day exceeding your {max_h}h limit: {days_list}.",
        "pl.wl.overloaded_many":    "Days exceeding your {max_h}h limit: {days_list}.",
        "pl.wl.within_limit":       "All days stay within your maximum hours per day.",
        "pl.wl.free_day_ok":        "{day} remains free as preferred.",
        "pl.wl.free_day_no":        "Note: {day} is not free in this plan.",
        "pl.wl.heavy_combo":        "Combined with your current enrolled courses, this may be a demanding schedule.",
        "pl.wl.no_data":            "No schedule data available.",

        # ── Planner — risk warnings ───────────────────────────────────
        "pl.risk.too_many":             "Adding {new} course(s) to your existing {existing} will likely create a heavy schedule. Consider starting with fewer courses.",
        "pl.risk.low_avg":              "Your current average performance score is {avg:.0f}/100. Taking multiple new courses may add pressure. We recommend starting with 1-2 new courses.",
        "pl.risk.high_risk_enrolled":   "You are currently flagged as high-risk in {n} enrolled course(s). Adding new courses now may make it harder to recover your performance.",
        "pl.risk.medium_risk_enrolled": "You have medium-risk predictions in {n} enrolled course(s). Keep your new course load manageable.",
        "pl.risk.critical_alert":       "A critical alert was recently raised: \"{alert_msg}\" — please review your current academic status before taking on more courses.",
        "pl.risk.recent_alerts":        "You have recent AI alerts in your academic record. Check them in your dashboard before finalizing your plan.",
        "pl.risk.day_overloaded":       "{day} is overloaded with {hours}h of classes, exceeding your {max_h}h daily limit.",
        "pl.risk.consecutive":          "{day} has {blocks} consecutive class blocks with little or no break. Consider if this is sustainable for you.",
        "pl.risk.very_heavy":           "You are already enrolled in many courses. Adding more may make it very difficult to maintain quality performance across all of them.",
        "pl.risk.no_schedule":          "No schedule data for: {courses}. These courses could not be fully analyzed for conflicts or workload.",

        # ── Planner — combination explanation ────────────────────────
        "pl.exp.rank1_high":        "This is your best schedule option.",
        "pl.exp.rank1_low":         "This is the highest-scoring valid combination found.",
        "pl.exp.rank2":             "This is a good alternative schedule.",
        "pl.exp.rank_other":        "This is a valid backup option.",
        "pl.exp.one_course":        "It includes {name}.",
        "pl.exp.multi_courses":     "It includes {n} courses: {names}.",
        "pl.exp.preferred_days":    "Covers your preferred days: {days}.",
        "pl.exp.free_day_ok":       "{day} stays free as requested.",
        "pl.exp.workload_balanced": "Weekly load: {h:.1f}h, balanced across {days} day(s).",
        "pl.exp.workload_overload": "Weekly load: {h:.1f}h. Watch out for {overloaded} — exceeds your daily limit.",
        "pl.exp.academic_strong":   "Based on your strong academic record (avg score: {avg:.0f}), this plan should be manageable.",
        "pl.exp.academic_good":     "Your recent academic performance (avg: {avg:.0f}) suggests you can handle this load with regular effort.",
        "pl.exp.academic_low":      "Your current academic average is {avg:.0f}. Focus on quality over quantity — this plan is achievable but requires commitment.",
        "pl.exp.partial_ctx":       "Recommendation includes partial academic context.",
        "pl.exp.schedule_only":     "Recommendation is based on schedule fit only (academic history is limited).",
        "pl.exp.critical_risk":     "Note: critical risk warnings apply — review them before requesting these courses.",

        # ── Planner — course recommendations ─────────────────────────
        "pl.rec.no_conflict":       "No schedule conflict with your current courses.",
        "pl.rec.conflict":          "This course conflicts with one of your current enrollments.",
        "pl.rec.preferred_days":    "Runs on your preferred days ({days}).",
        "pl.rec.free_day_used":     "Uses your preferred free day ({day}).",
        "pl.rec.too_early":         "Starts before 09:00 (early morning).",
        "pl.rec.too_late":          "Ends after 20:00 (late evening).",
        "pl.rec.day_overloaded":    "Would bring {day} over your {max_h}h daily limit.",
        "pl.rec.fits_limit":        "Fits within your daily hour limit ({dur:.1f}h).",
        "pl.rec.high_risk_multi":   "Your performance is flagged as high-risk in multiple courses.",
        "pl.rec.strong_avg":        "Your strong academic average ({avg:.0f}) suggests you can handle this.",
        "pl.rec.low_avg":           "Your current average is below 55 — adding more courses may be challenging.",
        "pl.rec.pos_feedback":      "You have positive feedback history in this course.",
        "pl.rec.neg_feedback":      "Recent feedback in this course was negative.",
        "pl.rec.schedule_fit":      "Schedule fit evaluated based on your preferences.",

        # ── Planner — result messages ─────────────────────────────────
        "pl.msg.not_enough":        "Need at least 2 published courses to analyze.",
        "pl.msg.invalid_ids":       " ({n} invalid course ID(s) were skipped.)",
        "pl.msg.all_conflict":      "All selected courses conflict with each other. No valid schedule found. Try removing conflicting courses.",
        "pl.msg.found_full":        "Found {total} valid combination(s). Showing top {top}. Personalized using your academic data.",
        "pl.msg.found_other":       "Found {total} valid combination(s). Showing top {top}. Based on schedule fit.",
        "pl.msg.recs_schedule_only":"Recommendations based on schedule fit only — no academic history found.",
        "pl.msg.recs_partial":      "Recommendations include partial academic context.",
        "pl.msg.recs_full":         "Recommendations personalized using your academic history.",

        # ── Claude fallback ───────────────────────────────────────────
        "cl.critical.explanation":  "Low attendance ({att:.1f}%) combined with low average grade ({avg:.1f}%) detected.",
        "cl.critical.action":       "Schedule an immediate review session and contact the student's parents.",
        "cl.declining.explanation": "Declining grades detected. Current average: {avg:.1f}%.",
        "cl.declining.action":      "Recommend additional study support and teacher check-in.",
        "cl.attendance.explanation":"Attendance below threshold: {att:.1f}%.",
        "cl.attendance.action":     "Contact student and parents regarding attendance.",
        "cl.stagnation.explanation":"Student scored below 60 in the last {n} lessons.",
        "cl.stagnation.action":     "Consider remedial sessions and check for learning difficulties.",
        "cl.info.explanation":      "Performance is {trend}. Average: {avg:.1f}%, Attendance: {att:.1f}%.",
        "cl.info.action":           "Continue monitoring progress.",
    },

    "he": {
        # ── Feedback analysis summary ─────────────────────────────────
        "fb.positive_with_tags":    "המשוב האחרון של המורה מדגיש {tag_str} חזק.",
        "fb.positive_no_tags":      "המשוב האחרון של המורה חיובי בדרך כלל.",
        "fb.negative_with_tags":    "המשוב האחרון של המורה מצביע על חששות בנוגע ל{tag_str}.",
        "fb.negative_no_tags":      "המשוב האחרון של המורה מצביע על תחומים הדורשים שיפור.",
        "fb.neutral_with_tags":     "המשוב האחרון של המורה מציין {tag_str} ממוצע.",
        "fb.neutral_no_tags":       "המשוב האחרון של המורה ניטרלי.",

        # ── Feedback trend ────────────────────────────────────────────
        "fbt.no_data":              "אין נתוני משוב זמינים לתקופה זו.",
        "fbt.neg_over_half":        "יותר ממחצית המשובים האחרונים ({neg_pct}%) שליליים.",
        "fbt.neg_moderate":         "{neg_pct}% מהמשובים האחרונים שליליים — יש לעקוב מקרוב.",
        "fbt.pos_majority":         "רוב המשובים חיוביים ({pos_pct}%).",
        "fbt.mixed":                "רגש המשובים מעורב.",
        "fbt.recurring_areas":      "תחומים חוזרים: {areas}.",
        "fbt.trend_worsening":      "המגמה מחמירה בהשוואה לתקופה הקודמת.",
        "fbt.trend_improving":      "המגמה משתפרת בהשוואה לתקופה הקודמת.",

        # ── Teacher assistant ─────────────────────────────────────────
        "ta.no_students":           "אין תלמידים פעילים רשומים לקורס זה.",
        "ta.class_avg":             "ממוצע הכיתה: {avg}/100.",
        "ta.excellent_count":       "{n} תלמיד(ים) מבצע(ים) בצורה מצוינת.",
        "ta.high_risk_count":       "{n} תלמיד(ים) בסיכון גבוה — נדרשת תשומת לב מיידית.",
        "ta.medium_risk_count":     "{n} תלמיד(ים) בסיכון בינוני — יש לעקוב מקרוב.",
        "ta.recent_alerts":         "{n} התראה(ות) בינה מלאכותית הועלו ב-14 הימים האחרונים.",
        "ta.all_normal":            "כל התלמידים נראים מתקדמים באופן תקין.",
        "ta.declining_trend":       "זוהתה מגמת ירידה עבור: {names}{suffix}.",
        "ta.improving_count":       "{n} תלמיד(ים) מראה(ים) מגמת שיפור.",
        "ta.group_review":          "יותר מ-30% מהכיתה זקוקים לתשומת לב — שקול לקיים שיעור חזרה קבוצתי.",
        "ta.recent_alert":          "התראה אחרונה: {message}",

        # ── Student insights panel ────────────────────────────────────
        "si.high_risk_courses":     "בסיכון גבוה ב-{n} קורס(ים) — מומלץ לפנות למורה לקבלת תמיכה.",
        "si.improving_courses":     "זוהתה מגמת שיפור ב-{n} קורס(ים).",
        "si.declining_courses":     "נרשמה ירידה בביצועים ב-{n} קורס(ים).",
        "si.feedback_concerns":     "המשוב האחרון מצביע על חששות בנושאים: {tag_str}.",
        "si.feedback_positive":     "משוב חיובי מדגיש: {tag_str}.",
        "si.perf_below_threshold":  "ביצועים מתחת לסף ב-{n} קורס(ים).",
        "si.strong_avg":            "ביצועים כוללים חזקים עם ממוצע של {avg}/100.",

        # ── Dashboard insights — teacher ──────────────────────────────
        "di.teacher.no_courses":    "עדיין אין קורסים פעילים. צור קורס כדי להתחיל לעקוב אחר התקדמות התלמידים.",
        "di.teacher.high_risk":     "{n} תלמיד(ים) בקורסים שלך נמצאים בסיכון גבוה — שקול לתזמן בדיקת מצב.",
        "di.teacher.needs_attn":    "{n} תלמיד(ים) זקוקים לתשומת לב על סמך נתוני ביצועים אחרונים.",
        "di.teacher.improving":     "{n} תלמיד(ים) מראים מגמת שיפור — מומנטום חיובי הראוי להכרה.",
        "di.teacher.best_course":   "הקורס החזק ביותר שלך כרגע הוא {course} (ממוצע {avg}/100).",
        "di.teacher.pos_feedback":  "מגמת המשוב האחרונה בקורסים שלך חיובית בעיקר.",
        "di.teacher.neg_feedback":  "המשוב האחרון מראה רגש שלילי יותר — שיעור חזרה קבוצתי עשוי לעזור.",
        "di.teacher.all_normal":    "כל התלמידים נראים מתקדמים באופן תקין. המשך כך!",

        # ── Dashboard insights — student ──────────────────────────────
        "di.student.avg_excellent": "הממוצע שלך בכל הקורסים הוא {avg}/100 — עבודה מצוינת!",
        "di.student.avg_solid":     "ציון הביצועים הממוצע שלך הוא {avg}/100 — התקדמות מוצקה עם מקום לצמיחה.",
        "di.student.avg_low":       "ציון הביצועים הממוצע שלך הוא {avg}/100 — מאמץ ממוקד על מושגי ליבה יכול לשפר זאת משמעותית.",
        "di.student.high_risk":     "אתה בסיכון גבוה ב-{n} קורס(ים) — מומלץ לפנות למורה שלך לקבלת תמיכה.",
        "di.student.improving":     "זוהה שיפור בביצועים ב-{n} קורס(ים) — המשך כך!",
        "di.student.declining":     "הביצועים יורדים ב-{n} קורס(ים) — עיין בחומר ובקש עזרה מוקדם.",
        "di.student.no_data":       "הנתונים האקדמיים שלך נמצאים במעקב. נוכחות עקבית ועבודה שוטפת יבנו תמונת התקדמות מלאה.",

        # ── Dashboard insights — parent ───────────────────────────────
        "di.parent.no_children":    "לא נמצאו ילדים מקושרים. פנה למנהל בית הספר שלך לקישור החשבון.",
        "di.parent.child_high_risk":"{child} נמצא בסיכון גבוה ב-{n} קורס(ים) — אנא פנה למורה.",
        "di.parent.child_improving":"{child} מראה מגמת שיפור ב-{n} קורס(ים).",
        "di.parent.child_alert":    "{child}: {message}",
        "di.parent.all_stable":     "לא זוהו התראות אחרונות או שינויים משמעותיים. הכול נראה יציב עבור ילדיך.",

        # ── Dashboard insights — admin ────────────────────────────────
        "di.admin.high_risk":       "{n} תלמיד(ים) נמצאים בסיכון אקדמי גבוה בפלטפורמה.",
        "di.admin.alerts":          "{n} התראה(ות) של בינה מלאכותית נוצרו ב-7 הימים האחרונים.",
        "di.admin.active_courses":  "{n} קורס(ים) פעיל(ים) כרגע בפלטפורמה.",
        "di.admin.at_risk_enroll":  "{n} רישום(ים) מראים מגמת ירידה — שקול סקירת התערבות מערכתית.",
        "di.admin.improving_enroll":"{n} רישום(ים) מראים שיפור — לפלטפורמה יש השפעה אקדמית חיובית.",
        "di.admin.stable":          "ביצועי המערכת נראים יציבים. לא זוהו דפוסים דחופים.",

        # ── Admin AI overview ─────────────────────────────────────────
        "ao.high_risk":             "{n} רישום(ים) בסיכון גבוה ({pct}% מהמעוקבים).",
        "ao.declining_courses":     "{n} קורס(ים) מראים מגמות ביצוע יורדות.",
        "ao.teacher_overload":      "{n} מורה(ים) מנהל(ים) 3+ קורסים פעילים.",
        "ao.stable":                "ביצועי המערכת נראים יציבים. לא זוהו דפוסים דחופים.",

        # ── Feedback suggestion — score + classification ──────────────
        "fs.score.excellent.encouraging":   "עבודה מצוינת! הציון הנוכחי שלך {val}/100 משקף מסירות יוצאת דופן וביצועים עקביים.",
        "fs.score.excellent.formal":        "הביצועים האקדמיים שלך ברמה מצוינת, עם ציון מורכב של {val}/100.",
        "fs.score.excellent.constructive":  "הציון הכולל שלך {val}/100 ממקם אותך בקטגוריית המצוין — תוצאה חזקה.",
        "fs.score.good.encouraging":        "אתה עושה טוב עם ציון של {val}/100 — המשך לבנות על הבסיס החזק הזה!",
        "fs.score.good.formal":             "ציון הביצועים הנוכחי שלך {val}/100 מדגים התקדמות יציבה וטובה.",
        "fs.score.good.constructive":       "הציון שלך {val}/100 משקף התקדמות מוצקה, עם מקום ברור לשיפור נוסף.",
        "fs.score.average.encouraging":     "אתה עושה התקדמות אמיתית עם ציון של {val}/100. במאמץ ממוקד, אני בטוח שתוכל להגיע לרמה הבאה.",
        "fs.score.average.formal":          "ציון הביצועים הנוכחי שלך הוא {val}/100, שהוא ברמה ממוצעת.",
        "fs.score.average.constructive":    "הציון שלך {val}/100 מצביע על ביצועים ממוצעים. חיזוק הרגלי הלמידה שלך יכול להוביל לשיפור משמעותי.",
        "fs.score.needs_attention.encouraging": "אני רוצה לפנות אליך כיוון שהציון הנוכחי שלך {val}/100 מצביע על אתגרים מסוימים — ואני מאמין שתוכל להפוך את המצב.",
        "fs.score.needs_attention.formal":      "ציון הביצועים הנוכחי שלך {val}/100 מצריך תשומת לב מיידית.",
        "fs.score.needs_attention.constructive":"הציון שלך {val}/100 מצביע שהקורס הזה זקוק למיקוד ומאמץ עקבי יותר כעת.",

        # ── Feedback suggestion — attendance ──────────────────────────
        "fs.att.low.encouraging":   "הנוכחות שלך הייתה נמוכה מהצפוי — נוכחות סדירה עושה הבדל משמעותי בהתקדמות הכוללת שלך.",
        "fs.att.low.formal":        "הנוכחות מהווה חשש (רכיב נוכחות: {att}/100). אנא תעדף השתתפות סדירה בשיעורים.",
        "fs.att.low.constructive":  "הנוכחות זקוקה לשיפור — אנא הפוך את ההשתתפות בשיעורים לעדיפות עקבית.",
        "fs.att.high":              "הנוכחות העקבית שלך ראויה לשבח ומשפיעה לטובה על הביצועים הכוללים שלך.",
        "fs.att.grades_low":        "למרות נוכחות סבירה, ניתן לחזק את הציונים באמצעות תרגול נוסף וסקירת חומר הקורס.",

        # ── Feedback suggestion — prediction ──────────────────────────
        "fs.pred.improving.encouraging": "אני רואה מגמת עלייה ברורה בביצועים שלך — המשך את המומנטום הזה!",
        "fs.pred.improving.other":       "מסלול הביצועים שלך נמצא במגמת שיפור. שמירה על עקביות זו תוביל לתוצאות מעולות.",
        "fs.pred.at_risk.encouraging":   "אני מאוד רוצה לראותך מתאושש — אל תהסס לפנות לתמיכה נוספת.",
        "fs.pred.at_risk.formal":        "על פי הנתונים הנוכחיים, מסלול ההתקדמות שלך מצריך התערבות. אנא קבע פגישה לדיון באפשרויות תמיכה אקדמית.",
        "fs.pred.at_risk.constructive":  "יש מגמת ירידה בביצועים שיש לטפל בה. מומלץ לחזור על מושגי ליבה ולבקש עזרה נוספת.",

        # ── Feedback suggestion — feedback history ────────────────────
        "fs.fb.neg.encouraging":    "משובים קודמים הדגישו תחומים כמו {area_str} — שיפורים ממוקדים קטנים כאן יכולים לעשות הבדל גדול.",
        "fs.fb.neg.other":          "תחומים הדורשים תשומת לב ממוקדת על סמך משובים קודמים: {areas}.",
        "fs.fb.pos":                "משוב חיובי מדגיש חוזקות ב: {areas}.",

        # ── Feedback suggestion — alerts ──────────────────────────────
        "fs.alert.attendance.encouraging": "שמתי לב להתראת נוכחות — הפיכת השיעורים לעדיפות עקבית תעזור לך להישאר על המסלול.",
        "fs.alert.feedback.encouraging":   "זכור: אתגרים הם חלק טבעי מהלמידה, ובקשת עזרה היא תמיד הצעד הנכון.",

        # ── Feedback suggestion — closings ────────────────────────────
        "fs.closing.encouraging":   "המשך לעשות מאמץ — אני כאן לתמוך בך בכל צעד!",
        "fs.closing.formal":        "אנא אל תהסס לפנות אלי אם תזדקק לסיוע אקדמי.",
        "fs.closing.constructive":  "אם יש לך שאלות או שאתה זקוק לתמיכה נוספת, אנא פנה אלינו בשעות הקבלה או דרך צ'אט הקורס.",

        # ── Feedback suggestion — empty fallbacks ─────────────────────
        "fs.empty.encouraging":     "המשך לעשות עבודה טובה! מאמץ עקבי ונוכחות סדירה בשיעורים הם המפתח להצלחה. אל תהסס לשאול שאלות כשאתה זקוק לתמיכה.",
        "fs.empty.formal":          "זהו אישור להשתתפותך בקורס זה. אנא הבטח מעורבות עקבית עם כל עבודת הקורס וצור איתי קשר אם תזדקק לתמיכה אקדמית.",
        "fs.empty.constructive":    "אנא הבטח נוכחות עקבית ומעורבות פעילה בחומר הקורס. פנה אלינו אם אתה זקוק לתמיכה או שיש לך שאלות לגבי התוכן.",

        # ── Planner — workload analysis ───────────────────────────────
        "pl.wl.adds_hours":         "תוכנית זו מוסיפה {h:.1f} שעות שבועיות על פני {days} יום(ים).",
        "pl.wl.overloaded_one":     "יום החורג ממגבלת {max_h} שעות שלך: {days_list}.",
        "pl.wl.overloaded_many":    "ימים החורגים ממגבלת {max_h} שעות שלך: {days_list}.",
        "pl.wl.within_limit":       "כל הימים נמצאים בתוך מספר השעות המרבי שלך ליום.",
        "pl.wl.free_day_ok":        "{day} נשאר פנוי כמבוקש.",
        "pl.wl.free_day_no":        "הערה: {day} אינו פנוי בתוכנית זו.",
        "pl.wl.heavy_combo":        "בשילוב עם הקורסים שאליהם אתה רשום כרגע, זה עלול להיות לוח זמנים תובעני.",
        "pl.wl.no_data":            "אין נתוני לוח זמנים זמינים.",

        # ── Planner — risk warnings ───────────────────────────────────
        "pl.risk.too_many":             "הוספת {new} קורס(ים) ל-{existing} הקיימים שלך עלולה ליצור לוח זמנים כבד. שקול להתחיל עם פחות קורסים.",
        "pl.risk.low_avg":              "ציון הביצועים הממוצע הנוכחי שלך הוא {avg:.0f}/100. לקיחת קורסים חדשים רבים עלולה להוסיף לחץ. אנו ממליצים להתחיל עם 1-2 קורסים חדשים.",
        "pl.risk.high_risk_enrolled":   "אתה מסומן כיום כבסיכון גבוה ב-{n} קורס(ים) שאליהם אתה רשום. הוספת קורסים חדשים עכשיו עלולה להקשות על שיקום הביצועים שלך.",
        "pl.risk.medium_risk_enrolled": "יש לך תחזיות סיכון בינוני ב-{n} קורס(ים) שאליהם אתה רשום. שמור על עומס קורסים ניתן לניהול.",
        "pl.risk.critical_alert":       "לאחרונה הועלתה התראה קריטית: \"{alert_msg}\" — אנא בדוק את המצב האקדמי הנוכחי שלך לפני לקיחת קורסים נוספים.",
        "pl.risk.recent_alerts":        "יש לך התראות בינה מלאכותית אחרונות בתיק האקדמי שלך. בדוק אותן בלוח הבקרה שלך לפני סיום התוכנית.",
        "pl.risk.day_overloaded":       "{day} עמוס עם {hours}h של שיעורים, החורג ממגבלת {max_h}h שלך ביום.",
        "pl.risk.consecutive":          "ב-{day} יש {blocks} בלוקים רצופים של שיעורים עם מנוחה קצרה או ללא מנוחה. שקול אם זה ברי-קיימא עבורך.",
        "pl.risk.very_heavy":           "אתה כבר רשום לקורסים רבים. הוספת עוד עלולה להקשות מאוד על שמירת ביצועים איכותיים בכולם.",
        "pl.risk.no_schedule":          "אין נתוני לוח זמנים עבור: {courses}. קורסים אלה לא ניתן לנתח לגמרי לגבי התנגשויות או עומס.",

        # ── Planner — combination explanation ────────────────────────
        "pl.exp.rank1_high":        "זו האפשרות הטובה ביותר עבורך.",
        "pl.exp.rank1_low":         "זהו הצירוף בעל הניקוד הגבוה ביותר שנמצא.",
        "pl.exp.rank2":             "זוהי חלופה טובה ללוח זמנים.",
        "pl.exp.rank_other":        "זוהי אפשרות גיבוי תקפה.",
        "pl.exp.one_course":        "הוא כולל את {name}.",
        "pl.exp.multi_courses":     "הוא כולל {n} קורסים: {names}.",
        "pl.exp.preferred_days":    "מכסה את הימים המועדפים שלך: {days}.",
        "pl.exp.free_day_ok":       "{day} נשאר פנוי כמבוקש.",
        "pl.exp.workload_balanced": "עומס שבועי: {h:.1f}h, מאוזן על פני {days} יום(ים).",
        "pl.exp.workload_overload": "עומס שבועי: {h:.1f}h. שים לב ל-{overloaded} — חורג ממגבלת היום שלך.",
        "pl.exp.academic_strong":   "בהתבסס על הרקע האקדמי החזק שלך (ממוצע: {avg:.0f}), תוכנית זו אמורה להיות ניתנת לניהול.",
        "pl.exp.academic_good":     "הביצועים האקדמיים האחרונים שלך (ממוצע: {avg:.0f}) מצביעים שתוכל להתמודד עם עומס זה במאמץ סדיר.",
        "pl.exp.academic_low":      "הממוצע האקדמי הנוכחי שלך הוא {avg:.0f}. התמקד באיכות על פני כמות — תוכנית זו ניתנת להשגה אבל דורשת מחויבות.",
        "pl.exp.partial_ctx":       "ההמלצה כוללת הקשר אקדמי חלקי.",
        "pl.exp.schedule_only":     "ההמלצה מבוססת על התאמת לוח זמנים בלבד (היסטוריה אקדמית מוגבלת).",
        "pl.exp.critical_risk":     "הערה: חלות אזהרות סיכון קריטיות — עיין בהן לפני שתבקש קורסים אלה.",

        # ── Planner — course recommendations ─────────────────────────
        "pl.rec.no_conflict":       "אין התנגשות לוח זמנים עם הקורסים הנוכחיים שלך.",
        "pl.rec.conflict":          "קורס זה מתנגש עם אחד מהרישומים הנוכחיים שלך.",
        "pl.rec.preferred_days":    "מתקיים בימים המועדפים שלך ({days}).",
        "pl.rec.free_day_used":     "משתמש ביום הפנוי המועדף שלך ({day}).",
        "pl.rec.too_early":         "מתחיל לפני 09:00 (בוקר מוקדם).",
        "pl.rec.too_late":          "מסתיים אחרי 20:00 (ערב מאוחר).",
        "pl.rec.day_overloaded":    "יביא את {day} מעל מגבלת {max_h}h שלך ביום.",
        "pl.rec.fits_limit":        "מתאים בתוך מגבלת השעות היומית שלך ({dur:.1f}h).",
        "pl.rec.high_risk_multi":   "הביצועים שלך מסומנים כסיכון גבוה בקורסים מרובים.",
        "pl.rec.strong_avg":        "הממוצע האקדמי החזק שלך ({avg:.0f}) מצביע שתוכל להתמודד עם זה.",
        "pl.rec.low_avg":           "הממוצע הנוכחי שלך מתחת ל-55 — הוספת קורסים נוספים עלולה להיות מאתגרת.",
        "pl.rec.pos_feedback":      "יש לך היסטוריית משוב חיובית בקורס זה.",
        "pl.rec.neg_feedback":      "המשוב האחרון בקורס זה היה שלילי.",
        "pl.rec.schedule_fit":      "התאמת לוח הזמנים הוערכה על סמך ההעדפות שלך.",

        # ── Planner — result messages ─────────────────────────────────
        "pl.msg.not_enough":        "נדרשים לפחות 2 קורסים שפורסמו לניתוח.",
        "pl.msg.invalid_ids":       " ({n} מזהה(י) קורס לא תקפים דולגו.)",
        "pl.msg.all_conflict":      "כל הקורסים הנבחרים מתנגשים זה בזה. לא נמצא לוח זמנים תקף. נסה להסיר קורסים מתנגשים.",
        "pl.msg.found_full":        "נמצאו {total} צירוף(ים) תקף(ים). מוצגים {top} המובילים. מותאם אישית תוך שימוש בנתונים האקדמיים שלך.",
        "pl.msg.found_other":       "נמצאו {total} צירוף(ים) תקף(ים). מוצגים {top} המובילים. מבוסס על התאמת לוח זמנים.",
        "pl.msg.recs_schedule_only":"המלצות מבוססות על התאמת לוח זמנים בלבד — לא נמצאה היסטוריה אקדמית.",
        "pl.msg.recs_partial":      "ההמלצות כוללות הקשר אקדמי חלקי.",
        "pl.msg.recs_full":         "ההמלצות מותאמות אישית תוך שימוש בהיסטוריה האקדמית שלך.",

        # ── Claude fallback ───────────────────────────────────────────
        "cl.critical.explanation":  "נוכחות נמוכה ({att:.1f}%) בשילוב עם ממוצע ציונים נמוך ({avg:.1f}%) זוהתה.",
        "cl.critical.action":       "קבע שיעור חזרה מיידי וצור קשר עם הורי התלמיד.",
        "cl.declining.explanation": "זוהתה ירידה בציונים. הממוצע הנוכחי: {avg:.1f}%.",
        "cl.declining.action":      "ממליץ על תמיכת לימוד נוספת ובדיקת מצב עם המורה.",
        "cl.attendance.explanation":"נוכחות מתחת לסף: {att:.1f}%.",
        "cl.attendance.action":     "צור קשר עם התלמיד וההורים בנוגע לנוכחות.",
        "cl.stagnation.explanation":"התלמיד קיבל מתחת ל-60 ב-{n} שיעורים האחרונים.",
        "cl.stagnation.action":     "שקול שיעורי תיקון ובדוק לקיים קשיי למידה.",
        "cl.info.explanation":      "הביצועים {trend}. ממוצע: {avg:.1f}%, נוכחות: {att:.1f}%.",
        "cl.info.action":           "המשך לעקוב אחר ההתקדמות.",
    },
}

# Hebrew trend labels (used in claude fallback info message)
_TREND_HE = {"stable": "יציבים", "improving": "משתפרים", "declining": "יורדים"}


def msg(key: str, lang: str = "en", **kw) -> str:
    """Look up a bilingual message template and format it with the given kwargs."""
    bank = _T.get(lang) or _T["en"]
    tpl  = bank.get(key) or _T["en"].get(key, key)
    try:
        return tpl.format(**kw) if kw else tpl
    except (KeyError, ValueError):
        # Fallback to English if format fails
        en_tpl = _T["en"].get(key, key)
        try:
            return en_tpl.format(**kw) if kw else en_tpl
        except Exception:
            return en_tpl


def trend_label(trend: str, lang: str = "en") -> str:
    """Translate a trend direction string for display."""
    if lang == "he":
        return _TREND_HE.get(trend, trend)
    return trend
