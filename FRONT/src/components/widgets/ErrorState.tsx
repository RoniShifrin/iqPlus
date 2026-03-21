import React from 'react';

interface Props {
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<Props> = ({ message = 'Something went wrong.', onRetry }) => (
  <div className="flex flex-col items-center justify-center py-16 text-center">
    <div className="text-4xl mb-3">⚠️</div>
    <p className="text-sm font-semibold text-red-600">{message}</p>
    {onRetry && (
      <button
        onClick={onRetry}
        className="mt-4 text-xs text-blue-600 border border-blue-200 rounded-lg px-4 py-1.5 hover:bg-blue-50 transition"
      >
        Try Again
      </button>
    )}
  </div>
);
