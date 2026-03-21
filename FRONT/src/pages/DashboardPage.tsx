import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const { t } = useApp();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      if (user?.role === 'student') {
        const courses = await apiService.getMyCourses();
        setData({ courses: courses.data });
      } else if (user?.role === 'teacher') {
        const courses = await apiService.getMyCourses();
        setData({ courses: courses.data });
      }
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Welcome, {user?.email}</h1>

      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <div className="bg-blue-100 p-6 rounded-lg">
          <h3 className="text-lg font-semibold text-blue-900">Role</h3>
          <p className="text-3xl font-bold text-blue-600 mt-2 capitalize">{user?.role}</p>
        </div>
        <div className="bg-green-100 p-6 rounded-lg">
          <h3 className="text-lg font-semibold text-green-900">Courses</h3>
          <p className="text-3xl font-bold text-green-600 mt-2">
            {data?.courses?.length || 0}
          </p>
        </div>
        <div className="bg-purple-100 p-6 rounded-lg">
          <h3 className="text-lg font-semibold text-purple-900">Status</h3>
          <p className="text-xl font-bold text-purple-600 mt-2">{t('enrollment.active')}</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">My Courses</h2>
        {data?.courses && data.courses.length > 0 ? (
          <div className="space-y-2">
            {data.courses.map((course: any) => (
              <div key={course.id} className="p-4 border rounded hover:bg-gray-50">
                <h3 className="font-semibold">{course.name}</h3>
                <p className="text-gray-600">{course.code}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">No courses yet</p>
        )}
      </div>
    </div>
  );
};
