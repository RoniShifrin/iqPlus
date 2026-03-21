import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';

export interface ConflictDetail {
  course_id: string;
  course_name: string;
  day: string;
  start_time: string;
  end_time: string;
}

interface Props {
  conflict: ConflictDetail;
  isParent?: boolean;
  onClose: () => void;
  onChooseChild?: () => void;
}

export const ConflictModal: React.FC<Props> = ({ conflict, isParent, onClose, onChooseChild }) => {
  const { t } = useApp();
  const navigate = useNavigate();

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-lg">⚠</div>
          <h2 className="text-lg font-bold text-gray-900">{t('conflictModal.title')}</h2>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          {t('conflictModal.body')}{' '}
          <span className="font-semibold text-gray-900">{conflict.course_name}</span>{' '}
          {t('conflictModal.on')}{' '}
          <span className="font-semibold text-gray-900">{conflict.day}</span>{' '}
          ({conflict.start_time}–{conflict.end_time})
        </p>

        <div className="flex flex-wrap gap-2 justify-end">
          {isParent && onChooseChild && (
            <button
              onClick={() => { onClose(); onChooseChild(); }}
              className="text-sm px-4 py-2 rounded-lg border border-indigo-300 text-indigo-700 hover:bg-indigo-50 transition"
            >
              {t('conflictModal.chooseChild')}
            </button>
          )}
          <button
            onClick={() => { onClose(); navigate(`/courses/${conflict.course_id}`); }}
            className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition"
          >
            {t('conflictModal.viewCourse')}
          </button>
          <button
            onClick={onClose}
            className="text-sm px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition"
          >
            {t('conflictModal.close')}
          </button>
        </div>
      </div>
    </div>
  );
};
