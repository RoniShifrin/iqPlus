import React, { createContext, useState, useEffect, ReactNode } from 'react';
import { safeStorage } from '../utils/safeStorage';

export interface AuthUser {
  id: string;
  uid: string;
  email: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  role?: string;
  avatar_url?: string;
  age?: number;
  linked_student_ids?: string[];
  is_approved?: boolean;
}

export interface SignupPayload {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  phone: string;
  role: string;
  subject?: string;
  employeeId?: string;
  grade?: string;
  dob?: string;
  parentContact?: string;
  childName?: string;
  childGrade?: string;
  relationship?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = safeStorage.getItem('auth_token');
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchCurrentUser = async () => {
    try {
      const token = safeStorage.getItem('auth_token');
      if (!token) { setLoading(false); return; }

      const res = await fetch(`${API}/api/me/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setUser({
          id: data.id,
          uid: data.firebase_uid,
          email: data.email,
          first_name: data.first_name,
          last_name: data.last_name,
          display_name: data.display_name,
          role: data.role,
          avatar_url: data.avatar_url,
          age: data.age,
          linked_student_ids: data.linked_student_ids,
        });
      } else {
        safeStorage.removeItem('auth_token');
      }
    } catch {
      console.error('Failed to fetch user');
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    setError(null);
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const msg = data.detail || 'Login failed';
      setError(msg);
      throw new Error(msg);
    }

    const data = await res.json();
    safeStorage.setItem('auth_token', data.access_token);
    await fetchCurrentUser();
  };

  const signup = async (payload: SignupPayload) => {
    setError(null);
    const res = await fetch(`${API}/api/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: payload.email,
        password: payload.password,
        first_name: payload.firstName,
        last_name: payload.lastName,
        phone: payload.phone,
        role: payload.role,
        subject: payload.subject,
        employee_id: payload.employeeId,
        grade: payload.grade,
        dob: payload.dob,
        parent_contact: payload.parentContact,
        child_name: payload.childName,
        child_grade: payload.childGrade,
        relationship: payload.relationship,
      }),
    });

    // 202 Accepted = registration submitted, pending admin approval (no token issued)
    if (res.status === 202) {
      const data = await res.json().catch(() => ({}));
      const msg = data.message || 'Registration submitted. Awaiting admin approval.';
      throw new Error(`PENDING:${msg}`);
    }

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const msg = data.detail || 'Registration failed';
      setError(msg);
      throw new Error(msg);
    }

    const data = await res.json();
    safeStorage.setItem('auth_token', data.access_token);
    await fetchCurrentUser();
  };

  const logout = async () => {
    safeStorage.removeItem('auth_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, login, signup, logout, refreshUser: fetchCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
