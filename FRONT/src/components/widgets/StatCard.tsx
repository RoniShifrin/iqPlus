import React from 'react';

interface Props {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string; // tailwind bg class e.g. 'bg-blue-500'
  sub?: string;
}

export const StatCard: React.FC<Props> = ({ label, value, icon, color = 'bg-blue-500', sub }) => (
  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex items-center gap-4">
    <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center text-white text-xl flex-shrink-0`}>
      {icon}
    </div>
    <div>
      <p className="text-2xl font-black text-gray-900 leading-none">{value}</p>
      <p className="text-xs text-gray-500 mt-1 font-medium">{label}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  </div>
);
