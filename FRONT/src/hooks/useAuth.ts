import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import React from 'react';

export const useAuthRedirect = () => {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (!loading && !user) {
      navigate('/login');
    }
  }, [user, loading, navigate]);

  return { user, loading };
};

export const useRole = (requiredRoles: string[]) => {
  const { user } = useAuth();
  return user && requiredRoles.includes(user.role || '');
};
