"""Email notification service"""
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailNotificationService:
    """Send email notifications for learning insights"""
    
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    
    @staticmethod
    def send_insight_notification(
        recipient_email: str,
        student_name: str,
        course_name: str,
        insight_summary: str,
        insight_type: str,
        recommendation: str
    ) -> bool:
        """Send learning insight notification email"""
        
        if not EmailNotificationService.SMTP_USER or not EmailNotificationService.SMTP_PASSWORD:
            logger.warning("Email service not configured, skipping notification")
            return False
        
        try:
            subject = f"Learning Insight: {insight_type.replace('_', ' ').title()} in {course_name}"
            
            html_body = EmailNotificationService._build_insight_email(
                student_name, course_name, insight_summary, recommendation
            )
            
            EmailNotificationService._send_smtp(recipient_email, subject, html_body)
            logger.info(f"Insight notification sent to {recipient_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    @staticmethod
    def _build_insight_email(student_name: str, course_name: str, summary: str, recommendation: str) -> str:
        """Build HTML email body for insight notification"""
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Learning Insight Alert</h2>
                    
                    <p>Hi {student_name},</p>
                    
                    <p>We've detected a significant change in your performance in <strong>{course_name}</strong>:</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                        <p><strong>{summary}</strong></p>
                    </div>
                    
                    <h3>Recommendation:</h3>
                    <p>{recommendation}</p>
                    
                    <p>Log in to IQ PLUS to view detailed progress analytics and more insights.</p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="font-size: 0.9em; color: #7f8c8d;">
                        This is an automated notification from IQ PLUS Learning Center Management System.<br>
                        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </div>
            </body>
        </html>
        """
        return html
    
    @staticmethod
    def _send_smtp(recipient: str, subject: str, html_body: str) -> None:
        """Send email via SMTP"""
        
        message = MIMEMultipart()
        message['From'] = EmailNotificationService.SMTP_USER
        message['To'] = recipient
        message['Subject'] = subject
        
        message.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(EmailNotificationService.SMTP_HOST, EmailNotificationService.SMTP_PORT) as server:
            server.starttls()
            server.login(EmailNotificationService.SMTP_USER, EmailNotificationService.SMTP_PASSWORD)
            server.send_message(message)
    
    @staticmethod
    def send_email(recipient: str, subject: str, html_content: str) -> bool:
        """Generic send_email entry point."""
        if not EmailNotificationService.SMTP_USER or not EmailNotificationService.SMTP_PASSWORD:
            logger.warning("Email service not configured, skipping send to %s", recipient)
            return False
        try:
            EmailNotificationService._send_smtp(recipient, subject, html_content)
            logger.info("Email sent to %s — %s", recipient, subject)
            return True
        except Exception as exc:
            logger.error("send_email failed for %s: %s", recipient, exc)
            return False

    @staticmethod
    def send_weekly_report(
        recipient_email: str,
        student_name: str,
        course_name: str,
        present: int,
        absent: int,
        avg_grade: float,
        trend: str,
        feedback_highlights: List[str],
        ai_observations: Optional[str] = None,
    ) -> bool:
        """Send a weekly academic summary to a teacher or parent."""
        subject = f"Weekly Report: {student_name} — {course_name}"
        feedback_html = "".join(f"<li>{f}</li>" for f in feedback_highlights) or "<li>No feedback this week.</li>"
        ai_section = (
            f'<h3>AI Observations</h3><p style="color:#d97706;">{ai_observations}</p>'
            if ai_observations else ""
        )
        trend_color = "#16a34a" if trend == "improving" else "#dc2626" if trend == "declining" else "#6b7280"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;line-height:1.6;">
          <div style="max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#1e40af;">IQ PLUS — Weekly Progress Report</h2>
            <p><strong>Student:</strong> {student_name}</p>
            <p><strong>Course:</strong> {course_name}</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <h3>Attendance</h3>
            <p>Present: <strong>{present}</strong>&nbsp;&nbsp;Absent: <strong>{absent}</strong></p>
            <h3>Average Grade</h3>
            <p style="font-size:1.4em;font-weight:bold;color:#1e40af;">{avg_grade:.1f}%</p>
            <h3>Trend</h3>
            <p style="color:{trend_color};font-weight:bold;text-transform:capitalize;">{trend}</p>
            <h3>Teacher Feedback Highlights</h3>
            <ul>{feedback_html}</ul>
            {ai_section}
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p style="font-size:0.85em;color:#9ca3af;">
              IQ PLUS Learning Center &mdash; {datetime.now().strftime('%Y-%m-%d')}
            </p>
          </div>
        </body></html>"""
        return EmailNotificationService.send_email(recipient_email, subject, body)

    @staticmethod
    def send_performance_warning(
        recipient_email: str,
        student_name: str,
        course_name: str,
        current_score: float,
        classification: str,
    ) -> bool:
        """Send a performance warning email when a student's score drops below a safe threshold."""
        subject = f"Performance Warning: {student_name} — {course_name}"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;line-height:1.6;">
          <div style="max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#dc2626;">IQ PLUS — Performance Warning</h2>
            <p><strong>Student:</strong> {student_name}</p>
            <p><strong>Course:</strong> {course_name}</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p>A performance concern has been detected:</p>
            <div style="background:#fef2f2;border-left:4px solid #dc2626;padding:12px 16px;margin:16px 0;">
              <p style="margin:0;font-weight:bold;">Current Score: {current_score:.1f}%
                &mdash; <span style="text-transform:capitalize;">{classification.replace('_', ' ')}</span>
              </p>
            </div>
            <p>Please review the student's progress and consider additional support.</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p style="font-size:0.85em;color:#9ca3af;">
              IQ PLUS Learning Center &mdash; {datetime.now().strftime('%Y-%m-%d')}
            </p>
          </div>
        </body></html>"""
        return EmailNotificationService.send_email(recipient_email, subject, body)

    @staticmethod
    def send_improvement_notification(
        recipient_email: str,
        student_name: str,
        course_name: str,
        previous_score: float,
        current_score: float,
    ) -> bool:
        """Send an improvement notification email when a student shows significant progress."""
        subject = f"Progress Improvement: {student_name} — {course_name}"
        change = current_score - previous_score
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;line-height:1.6;">
          <div style="max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#16a34a;">IQ PLUS — Performance Improvement</h2>
            <p><strong>Student:</strong> {student_name}</p>
            <p><strong>Course:</strong> {course_name}</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p>Great news! A significant improvement has been detected:</p>
            <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:12px 16px;margin:16px 0;">
              <p style="margin:0;font-weight:bold;">
                Score improved from {previous_score:.1f}% to {current_score:.1f}%
                (+{change:.1f}%)
              </p>
            </div>
            <p>Keep up the excellent work!</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p style="font-size:0.85em;color:#9ca3af;">
              IQ PLUS Learning Center &mdash; {datetime.now().strftime('%Y-%m-%d')}
            </p>
          </div>
        </body></html>"""
        return EmailNotificationService.send_email(recipient_email, subject, body)

    @staticmethod
    def send_teacher_feedback_notification(
        recipient_email: str,
        student_name: str,
        course_name: str,
        sentiment: str,
        feedback_preview: str,
    ) -> bool:
        """Send notification email when a teacher submits feedback for a student."""
        sentiment_color = {"positive": "#16a34a", "neutral": "#6b7280", "negative": "#dc2626"}.get(
            sentiment.lower(), "#6b7280"
        )
        subject = f"Teacher Feedback: {student_name} — {course_name}"
        body = f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;line-height:1.6;">
          <div style="max-width:600px;margin:0 auto;padding:20px;">
            <h2 style="color:#1e40af;">IQ PLUS — New Teacher Feedback</h2>
            <p><strong>Student:</strong> {student_name}</p>
            <p><strong>Course:</strong> {course_name}</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p><strong>Sentiment:</strong>
              <span style="color:{sentiment_color};font-weight:bold;text-transform:capitalize;">
                {sentiment}
              </span>
            </p>
            <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:12px 16px;margin:16px 0;">
              <p style="margin:0;">{feedback_preview}</p>
            </div>
            <p>Log in to IQ PLUS to view the full feedback details.</p>
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
            <p style="font-size:0.85em;color:#9ca3af;">
              IQ PLUS Learning Center &mdash; {datetime.now().strftime('%Y-%m-%d')}
            </p>
          </div>
        </body></html>"""
        return EmailNotificationService.send_email(recipient_email, subject, body)

    @staticmethod
    def send_batch_notifications(insights: List[dict]) -> dict:
        """Send notifications for multiple insights"""
        
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0
        }
        
        for insight in insights:
            try:
                success = EmailNotificationService.send_insight_notification(
                    recipient_email=insight['recipient_email'],
                    student_name=insight['student_name'],
                    course_name=insight['course_name'],
                    insight_summary=insight['summary'],
                    insight_type=insight['insight_type'],
                    recommendation=insight['recommendation']
                )
                
                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
                results['failed'] += 1
        
        return results
