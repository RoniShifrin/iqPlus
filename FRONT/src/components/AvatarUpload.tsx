import React, { useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { apiService } from '../services/apiService';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const MAX_SIZE = 2 * 1024 * 1024; // 2 MB
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];

interface Props {
  size?: number; // px, default 80
}

export const AvatarUpload: React.FC<Props> = ({ size = 80 }) => {
  const { user, refreshUser } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const avatarSrc = user?.avatar_url
    ? `${API}${user.avatar_url}`
    : null;

  const initials = (() => {
    const name = user?.display_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.email || '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  })();

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');

    if (!ALLOWED.includes(file.type)) {
      setError('Only JPG, PNG, or WebP images are allowed.');
      return;
    }
    if (file.size > MAX_SIZE) {
      setError('Image must be under 2 MB.');
      return;
    }

    try {
      setUploading(true);
      await apiService.uploadAvatar(file);
      await refreshUser();
    } catch {
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="relative cursor-pointer group"
        style={{ width: size, height: size }}
        onClick={() => inputRef.current?.click()}
        title="Click to upload avatar"
      >
        {avatarSrc ? (
          <img
            src={avatarSrc}
            alt="Avatar"
            className="rounded-full object-cover w-full h-full ring-2 ring-white"
          />
        ) : (
          <div
            className="rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold ring-2 ring-white"
            style={{ width: size, height: size, fontSize: size * 0.32 }}
          >
            {initials}
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
          {uploading ? (
            <span className="text-white text-xs">...</span>
          ) : (
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          )}
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={handleFile}
      />

      {error && <p className="text-red-500 text-xs text-center max-w-[120px]">{error}</p>}
    </div>
  );
};
