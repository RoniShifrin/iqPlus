import axios, { AxiosInstance } from 'axios';
import { safeStorage } from '../utils/safeStorage';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_URL,
    headers: { 'Content-Type': 'application/json' },
  });

  client.interceptors.request.use((config) => {
    const token = safeStorage.getItem('auth_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        safeStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }
  );

  return client;
};

export const apiClient = createApiClient();

export const apiService = {
  // ── Profile ──────────────────────────────────────────────────────────────
  getProfile:        ()                  => apiClient.get('/api/me/profile'),
  getUserProfile:    (userId: string)    => apiClient.get(`/api/users/${userId}/profile`),
  updateProfile: (data: any)         => apiClient.put('/api/me/profile', data),
  uploadAvatar:  (file: File)        => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post('/api/me/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // ── Dashboard ────────────────────────────────────────────────────────────
  getDashboard:        ()             => apiClient.get('/api/dashboard'),
  getDashboardUpdates: ()             => apiClient.get('/api/dashboard/updates'),

  // ── Course Detail ────────────────────────────────────────────────────────
  getCourseDetail: (courseId: string) => apiClient.get(`/api/courses/${courseId}/detail`),

  // ── Courses ─────────────────────────────────────────────────────────────
  getCourses:      ()                  => apiClient.get('/api/courses/'),
  getMyCourses:    ()                  => apiClient.get('/api/courses/my-courses'),
  getParentCourses: ()                 => apiClient.get('/api/parent/courses'),
  getCourse:       (id: string)        => apiClient.get(`/api/courses/${id}`),
  createCourse:    (data: any)         => apiClient.post('/api/courses/', data),
  updateCourse:    (id: string, data: any) => apiClient.put(`/api/courses/${id}`, data),
  deleteCourse:    (id: string)        => apiClient.delete(`/api/courses/${id}`),
  publishCourse:   (id: string)        => apiClient.post(`/api/courses/${id}/publish`),
  archiveCourse:   (id: string)        => apiClient.post(`/api/courses/${id}/archive`),
  restoreCourse:   (id: string)        => apiClient.post(`/api/courses/${id}/restore`),

  // ── Enrollments ─────────────────────────────────────────────────────────
  enrollCourse:    (data: any)         => apiClient.post('/api/enrollments/', data),
  getEnrollments:  (filters?: any)     => apiClient.get('/api/enrollments/', { params: filters }),
  withdrawCourse:  (id: string)        => apiClient.delete(`/api/enrollments/${id}`),

  // ── Progress & Insights ─────────────────────────────────────────────────
  getStudentProgress: (studentId: string, courseId: string) =>
    apiClient.get(`/api/progress/student/${studentId}`, { params: { course_id: courseId } }),
  getInsights: (studentId?: string) =>
    apiClient.get('/api/progress/insights', { params: { student_id: studentId } }),

  // ── Academic ────────────────────────────────────────────────────────────
  recordGrade:      (data: any)        => apiClient.post('/api/academic/grades', data),
  getGrades:        (filters?: any)    => apiClient.get('/api/academic/grades', { params: filters }),
  recordAttendance: (data: any)        => apiClient.post('/api/academic/attendance', data),
  getAttendance:    (filters?: any)    => apiClient.get('/api/academic/attendance', { params: filters }),
  submitFeedback:   (data: any)        => apiClient.post('/api/academic/feedback', data),
  getFeedback:      (courseId?: string)=>
    apiClient.get('/api/academic/feedback', { params: { course_id: courseId } }),
  getGradeSuggestions: (courseId: string) =>
    apiClient.get('/api/academic/grade-suggestions', { params: { course_id: courseId } }),
  approveGradeSuggestion: (suggestionId: string) =>
    apiClient.post(`/api/academic/grade-suggestions/${suggestionId}/approve`),
  rejectGradeSuggestion:  (suggestionId: string) =>
    apiClient.post(`/api/academic/grade-suggestions/${suggestionId}/reject`),

  // ── Notifications ────────────────────────────────────────────────────────
  getNotifications:    ()              => apiClient.get('/api/notifications/'),
  getAllNotifications:  (limit = 100)  => apiClient.get('/api/notifications/', { params: { limit } }),
  getUnreadCount:      ()              => apiClient.get('/api/notifications/unread-count'),
  markNotificationRead:(id: string)   => apiClient.patch(`/api/notifications/${id}/read`),
  markAllRead:         ()              => apiClient.post('/api/notifications/read-all'),

  // ── Enrollment flow ──────────────────────────────────────────────────────
  requestEnrollment:   (courseId: string, studentId?: string) => apiClient.post('/api/enrollments/request', { course_id: courseId, ...(studentId ? { student_id: studentId } : {}) }),
  getPendingTeacherRequests: () => apiClient.get('/api/enrollments/pending-teacher'),
  approveEnrollment:   (id: string, reason?: string) => apiClient.post(`/api/enrollments/${id}/approve`, { reason }),
  rejectEnrollment:    (id: string, reason?: string) => apiClient.post(`/api/enrollments/${id}/reject`, { reason }),

  // ── Course Materials ─────────────────────────────────────────────────────
  getMaterials:    (courseId: string)  => apiClient.get(`/api/courses/${courseId}/materials`),
  addMaterial:     (courseId: string, data: FormData) =>
    apiClient.post(`/api/courses/${courseId}/materials`, data, { headers: { 'Content-Type': 'multipart/form-data' } }),
  deleteMaterial:  (courseId: string, materialId: string) =>
    apiClient.delete(`/api/courses/${courseId}/materials/${materialId}`),

  // ── Search ───────────────────────────────────────────────────────────────
  search: (q: string, type?: string)  => apiClient.get('/api/search/', { params: { q, type } }),

  // ── Audit Logs (admin) ── now in Admin section above ────────────────────

  // ── Lesson Records ───────────────────────────────────────────────────────
  createLessonRecord: (data: any) => apiClient.post('/api/lesson-records/', data),
  getLessonRecords: (studentId?: string, courseId?: string) =>
    apiClient.get('/api/lesson-records/', { params: { student_id: studentId, course_id: courseId } }),

  // ── AI Alerts ────────────────────────────────────────────────────────────
  getAIAlerts: (params?: { student_id?: string; course_id?: string }) =>
    apiClient.get('/api/ai-alerts/', { params }),

  // ── Reports export ───────────────────────────────────────────────────────
  exportStudentReport: (studentId: string, format: 'pdf' | 'csv' | 'xlsx') =>
    apiClient.get(`/api/reports/student/${studentId}/export`, {
      params: { format },
      responseType: 'blob',
    }),
  exportCourseReport: (courseId: string, format: 'csv' | 'xlsx' = 'csv') =>
    apiClient.get(`/api/reports/course/${courseId}/export`, {
      params: { format },
      responseType: 'blob',
    }),
  exportAttendanceReport: (courseId: string, format: 'csv' | 'xlsx' = 'csv', studentId?: string) =>
    apiClient.get(`/api/reports/attendance/${courseId}/export`, {
      params: { format, ...(studentId ? { student_id: studentId } : {}) },
      responseType: 'blob',
    }),

  // ── Admin ─────────────────────────────────────────────────────────────────
  getSystemHealth: () => apiClient.get('/api/admin/system-health'),
  getAdminStudents: () => apiClient.get('/api/search/', { params: { q: '', type: 'students' } }),
  getAuditLogs: (params?: { limit?: number; skip?: number; action?: string; resource_type?: string; user_id?: string }) =>
    apiClient.get('/api/audit-logs/', { params }),

  // ── Admin User Management ─────────────────────────────────────────────────
  getAdminUsers: (role?: string) =>
    apiClient.get('/api/admin/users/', { params: role ? { role } : {} }),
  getPendingUsers: () => apiClient.get('/api/admin/users/pending'),
  adminCreateUser: (data: { email: string; first_name: string; last_name: string; password: string; role: string }) =>
    apiClient.post('/api/admin/users/create', data),
  approveUser: (userId: string, role?: string) =>
    apiClient.patch(`/api/admin/users/${userId}/approve`, role ? { role } : {}),
  rejectUser:  (userId: string) => apiClient.patch(`/api/admin/users/${userId}/reject`),
  deactivateUser:   (userId: string) => apiClient.patch(`/api/admin/users/${userId}/deactivate`),
  activateUser:     (userId: string) => apiClient.patch(`/api/admin/users/${userId}/activate`),
  deleteUser:       (userId: string) => apiClient.delete(`/api/admin/users/${userId}`),
  getUserCourses:   (userId: string) => apiClient.get(`/api/admin/users/${userId}/courses`),
  changeUserRole:   (userId: string, role: string) =>
    apiClient.patch(`/api/admin/users/${userId}/role`, { role }),
  changeCourseTeacher: (courseId: string, teacherId: string) =>
    apiClient.patch(`/api/courses/${courseId}/teacher`, { teacher_id: teacherId }),

  // ── Performance Scores ───────────────────────────────────────────────────
  getScore: (studentId: string, courseId: string) =>
    apiClient.get(`/api/scores/${studentId}/${courseId}`),
  getStudentScores: (studentId: string) =>
    apiClient.get(`/api/scores/${studentId}`),
  getScoreHistory: (studentId: string, courseId: string, limit = 20) =>
    apiClient.get(`/api/scores/${studentId}/${courseId}/history`, { params: { limit } }),
  getFeedbackInsight: (studentId: string, courseId: string) =>
    apiClient.get(`/api/scores/${studentId}/${courseId}/feedback-insight`),
  getPrediction: (studentId: string, courseId: string) =>
    apiClient.get(`/api/scores/${studentId}/${courseId}/prediction`),
  getAllPredictions: (studentId: string) =>
    apiClient.get(`/api/scores/${studentId}/predictions`),
  forceComputeScore: (studentId: string, courseId: string) =>
    apiClient.post(`/api/scores/${studentId}/${courseId}/compute`),

  // ── Course Announcements ─────────────────────────────────────────────────
  announceCourse: (courseId: string, data: { subject: string; content: string; include_parents: boolean }) =>
    apiClient.post(`/api/courses/${courseId}/announce`, data),

  // ── Messages ─────────────────────────────────────────────────────────────
  sendMessage: (data: any) => apiClient.post('/api/messages/', data),
  getInbox: (limit = 50) => apiClient.get('/api/messages/inbox', { params: { limit } }),
  getSentMessages: (limit = 50) => apiClient.get('/api/messages/sent', { params: { limit } }),
  markMessageRead: (messageId: string) => apiClient.put(`/api/messages/${messageId}/read`),
  getMessageContacts: () => apiClient.get('/api/messages/contacts'),

  // ── Syllabus ─────────────────────────────────────────────────────────────
  getSyllabus: (courseId: string) => apiClient.get(`/api/syllabus/${courseId}`),
  getMilestones: (courseId: string) => apiClient.get(`/api/syllabus/${courseId}/milestones`),
  createSyllabus: (data: any) => apiClient.post('/api/syllabus/', data),
  updateSyllabus: (syllabusId: string, data: any) => apiClient.put(`/api/syllabus/${syllabusId}`, data),
  publishSyllabus: (syllabusId: string) => apiClient.put(`/api/syllabus/${syllabusId}/publish`),
  completeWeek: (syllabusId: string, weekNumber: number) =>
    apiClient.post(`/api/syllabus/${syllabusId}/complete-week`, { week_number: weekNumber }),

  // ── Usability Feedback ───────────────────────────────────────────────────
  submitUsabilityFeedback: (data: any) => apiClient.post('/api/usability/feedback', data),
  getUsabilityFeedback: (limit = 100) => apiClient.get('/api/usability/feedback', { params: { limit } }),
  getUsabilitySummary: () => apiClient.get('/api/usability/feedback/summary'),

  // ── Chat ─────────────────────────────────────────────────────────────────
  startConversation: (data: { type: 'direct' | 'course'; participant_id?: string; course_id?: string }) =>
    apiClient.post('/api/chat/conversations', data),
  getConversations: () => apiClient.get('/api/chat/conversations'),
  getChatContacts: (courseId?: string) =>
    apiClient.get('/api/chat/contacts', courseId ? { params: { course_id: courseId } } : undefined),
  getChatPresence: (userIds: string[]) =>
    apiClient.get('/api/chat/presence', { params: { user_ids: userIds.join(',') } }),
  getChatMessages: (convId: string, limit = 50) =>
    apiClient.get(`/api/chat/conversations/${convId}/messages`, { params: { limit } }),
  sendChatMessage: (convId: string, content: string) =>
    apiClient.post(`/api/chat/conversations/${convId}/messages`, { content }),
  markConversationRead: (convId: string) =>
    apiClient.post(`/api/chat/conversations/${convId}/read`),

  // ── AI Intelligence Layer ─────────────────────────────────────────────────
  getCourseRiskSummary:   (courseId: string) =>
    apiClient.get('/api/ai/risk-summary', { params: { course_id: courseId } }),
  getTeacherAssistant:   (courseId: string) =>
    apiClient.get(`/api/ai/teacher-assistant/${courseId}`),
  getAdminAIOverview:    () =>
    apiClient.get('/api/ai/admin-overview'),
  getStudentAIInsights:  (studentId: string) =>
    apiClient.get(`/api/ai/student-insights/${studentId}`),
  getFeedbackTrend:      (courseId: string, days = 60) =>
    apiClient.get(`/api/ai/feedback-trend/${courseId}`, { params: { days } }),
  suggestFeedback:       (data: { student_id: string; course_id: string; tone: string }) =>
    apiClient.post('/api/ai/suggest-feedback', data),
  getDashboardInsights:  () =>
    apiClient.get('/api/ai/dashboard-insights'),

  // ── AI Alert interactions ─────────────────────────────────────────────────
  markAlertSeen:         (alertId: string) =>
    apiClient.post(`/api/ai-alerts/${alertId}/seen`),
  acknowledgeAlert:      (alertId: string, comment?: string) =>
    apiClient.post(`/api/ai-alerts/${alertId}/acknowledge`, { comment: comment ?? '' }),

  // ── Academic Planner ──────────────────────────────────────────────────────
  analyzeSchedule: (data: {
    course_ids: string[];
    student_id?: string;
    preferences?: {
      preferred_days?: string[];
      preferred_free_day?: string;
      preferred_start_hour?: number;
      preferred_end_hour?: number;
      max_courses?: number;
      max_hours_per_day?: number;
      avoid_early?: boolean;
      avoid_late?: boolean;
    };
  }) => apiClient.post('/api/planner/analyze', data),
  getPlannerRecommendations: (params?: {
    student_id?: string;
    avoid_early?: boolean;
    avoid_late?: boolean;
    max_hours_day?: number;
  }) => apiClient.get('/api/planner/recommendations', { params }),
};
