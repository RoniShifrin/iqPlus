import React from 'react';

interface Props {
  icon?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<Props> = ({ icon = '📭', title, description, action }) => (
  <div className="flex flex-col items-center justify-center py-16 text-center text-gray-400">
    <div className="text-5xl mb-3">{icon}</div>
    <p className="font-semibold text-gray-600 text-sm">{title}</p>
    {description && <p className="text-xs mt-1 max-w-xs">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);
