import React from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface UserAvatarProps {
  name: string;
  url?: string | null;
  size: number;
  /** Tailwind background class — used only when url is absent. Default: blue-purple gradient. */
  bg?: string;
}

/**
 * Renders a round avatar: real profile image if url is present, otherwise an initials circle.
 * Reused across admin/teacher/course/parent user lists.
 */
export const UserAvatar: React.FC<UserAvatarProps> = ({
  name,
  url,
  size,
  bg = 'bg-gradient-to-br from-blue-300 to-purple-400',
}) => {
  const initials = name
    .split(' ')
    .map(w => w[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?';

  if (url) {
    return (
      <img
        src={`${API_URL}${url}`}
        alt={name}
        className="rounded-full object-cover flex-shrink-0"
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <div
      className={`rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 ${bg}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.35) }}
    >
      {initials}
    </div>
  );
};
