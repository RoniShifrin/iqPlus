"""AI-powered learning insights and analysis"""
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class LearningProfileBuilder:
    """Build comprehensive learning profiles from academic data"""
    
    @staticmethod
    def build_profile(grades: list, attendance: list) -> dict:
        """
        Build learning profile from grades and attendance
        
        Returns:
            {
                'performance_level': 'strong' | 'average' | 'needs_improvement',
                'consistency_score': 0-100,
                'attendance_reliability': 0-100,
                'risk_indicators': []
            }
        """
        if not grades:
            return {
                'performance_level': 'unknown',
                'consistency_score': 0,
                'attendance_reliability': 0,
                'risk_indicators': ['No grade data']
            }
        
        scores = [g.score for g in grades]
        avg_score = sum(scores) / len(scores)
        
        # Performance level
        if avg_score >= 80:
            performance_level = 'strong'
        elif avg_score >= 60:
            performance_level = 'average'
        else:
            performance_level = 'needs_improvement'
        
        # Consistency score
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        consistency = max(0, 100 - (variance / avg_score * 10))
        
        # Attendance reliability
        if attendance:
            attendance_reliability = (len([a for a in attendance if a.status in ['present', 'late']]) / len(attendance)) * 100
        else:
            attendance_reliability = 0
        
        # Risk indicators
        risk_indicators = []
        if avg_score < 50:
            risk_indicators.append('Low overall grades')
        if len([s for s in scores if s < avg_score - 20]) > 0:
            risk_indicators.append('Inconsistent performance')
        if attendance_reliability < 75:
            risk_indicators.append('Attendance concerns')
        
        return {
            'performance_level': performance_level,
            'consistency_score': round(consistency, 2),
            'attendance_reliability': round(attendance_reliability, 2),
            'risk_indicators': risk_indicators,
            'average_score': round(avg_score, 2)
        }

class ChangeDetector:
    """Detect significant changes in student performance"""
    
    THRESHOLD = 15.0  # 15% change
    
    @staticmethod
    def detect_performance_change(current_avg: float, previous_avg: float) -> Optional[dict]:
        """
        Detect if there's a significant change in performance
        
        Returns:
            {
                'detected': bool,
                'change_percent': float,
                'direction': 'improvement' | 'decline',
                'severity': 'minor' | 'moderate' | 'severe'
            }
        """
        if previous_avg == 0:
            return None
        
        change_pct = ((current_avg - previous_avg) / previous_avg) * 100
        
        return {
            'detected': abs(change_pct) >= ChangeDetector.THRESHOLD,
            'change_percent': round(change_pct, 2),
            'direction': 'improvement' if change_pct > 0 else 'decline',
            'severity': ChangeDetector._assess_severity(abs(change_pct))
        }
    
    @staticmethod
    def _assess_severity(change_pct: float) -> str:
        if change_pct < 25:
            return 'minor'
        elif change_pct < 50:
            return 'moderate'
        else:
            return 'severe'

class InsightGenerator:
    """Generate explainable, actionable insights"""
    
    @staticmethod
    def generate_grade_insight(student_name: str, change_pct: float, current_avg: float, subject: str = "overall") -> dict:
        """Generate insight summary for grade changes"""
        
        is_improvement = change_pct > 0
        abs_change = abs(change_pct)
        
        if is_improvement:
            if abs_change > 30:
                summary = f"Exceptional improvement in {subject} grades!"
                recommendation = "Keep up the excellent work. Consider helping peers who may be struggling."
            else:
                summary = f"Good improvement in {subject} performance."
                recommendation = "Continue your current study habits and maintain this momentum."
        else:
            if abs_change > 30:
                summary = f"Significant decline in {subject} grades detected."
                recommendation = "Reach out to your teacher immediately for additional support and tutoring."
            else:
                summary = f"Decline in {subject} performance."
                recommendation = "Review recent lessons and consider forming a study group."
        
        return {
            'summary': summary,
            'recommendation': recommendation,
            'change_percent': round(change_pct, 2),
            'current_average': round(current_avg, 2),
            'explainable': True  # Mark as explainable for transparency
        }
    
    @staticmethod
    def generate_attendance_insight(student_name: str, current_rate: float, previous_rate: float) -> dict:
        """Generate insight summary for attendance changes"""
        
        change_pct = ((current_rate - previous_rate) / previous_rate) * 100 if previous_rate > 0 else 0
        is_improvement = change_pct > 0
        
        if is_improvement:
            summary = f"{student_name}'s attendance has improved significantly."
            recommendation = "Great job! Regular attendance is key to academic success."
        else:
            if current_rate < 80:
                summary = f"{student_name} is at risk due to low attendance ({current_rate:.1f}%)."
                recommendation = "Regular attendance is mandatory. Please prioritize attending all classes."
            else:
                summary = f"{student_name}'s attendance has slightly declined."
                recommendation = "Make an effort to attend all scheduled classes."
        
        return {
            'summary': summary,
            'recommendation': recommendation,
            'current_rate': round(current_rate, 2),
            'previous_rate': round(previous_rate, 2),
            'explainable': True
        }

class NotificationTrigger:
    """Determine when to send notifications"""
    
    @staticmethod
    def should_notify(insight_type: str, severity: str) -> bool:
        """
        Determine if notification should be sent
        
        Only sends for significant changes (moderate or severe)
        """
        significant_severities = ['moderate', 'severe']
        significant_types = [
            'performance_improvement',
            'performance_decline',
            'attendance_concern',
            'attendance_improvement'
        ]
        
        return insight_type in significant_types and severity in significant_severities
    
    @staticmethod
    def get_notification_recipients(student, course_teacher) -> list:
        """Get user IDs for in-app notifications (no PII passed to AI layer)."""
        recipients = [str(student.id)]
        if course_teacher:
            recipients.append(str(course_teacher.id))
        return recipients

logger.info("AI Service initialized with change detection threshold: 15%")
