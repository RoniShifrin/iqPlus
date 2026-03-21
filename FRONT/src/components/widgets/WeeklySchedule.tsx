import React from 'react';
import { useApp } from '../../contexts/AppContext';

export interface ScheduleSlot {
  id?: string;   // course id — used for click navigation
  day: string;   // 'Sunday' | 'Monday' | ... (English key, as stored in DB)
  time: string;  // '9:00 AM'
  course: string;
  teacher?: string;
  color: string; // tailwind bg class
}

// All days in Israeli school-week order (Sun–Fri)
const ALL_DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

// Translation key map for abbreviated day labels
const DAY_T_KEY: Record<string, string> = {
  Sunday:    'day.sun',
  Monday:    'day.mon',
  Tuesday:   'day.tue',
  Wednesday: 'day.wed',
  Thursday:  'day.thu',
  Friday:    'day.fri',
};

// English fallback abbreviations
const DAY_FALLBACK: Record<string, string> = {
  Sunday: 'Sun', Monday: 'Mon', Tuesday: 'Tue',
  Wednesday: 'Wed', Thursday: 'Thu', Friday: 'Fri',
};

// Default time rows shown when no slots exist
const DEFAULT_TIMES = ['9:00 AM', '10:00 AM', '11:00 AM', '1:00 PM', '3:00 PM'];

interface Props {
  slots: ScheduleSlot[];
  highlightToday?: boolean;
  onSlotClick?: (slot: ScheduleSlot) => void;
}

/** Convert a time string like "9:00 AM" to total minutes for sorting */
function toMinutes(t: string): number {
  const [time, period] = t.split(' ');
  const [h, m] = time.split(':').map(Number);
  const h24 = period === 'PM' && h !== 12 ? h + 12 : period === 'AM' && h === 12 ? 0 : h;
  return h24 * 60 + (m || 0);
}

export const WeeklySchedule: React.FC<Props> = ({ slots, highlightToday = true, onSlotClick }) => {
  const { t } = useApp();
  const todayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][new Date().getDay()];

  // Show only days that have at least one scheduled slot (avoids blank columns)
  const daysWithSlots = ALL_DAYS.filter(d => slots.some(s => s.day === d));
  const displayDays = daysWithSlots.length > 0 ? daysWithSlots : ALL_DAYS;

  // Build time rows dynamically from slot times; fall back to default set if no data
  const uniqueTimes = [...new Set(slots.map(s => s.time))];
  const displayTimes = uniqueTimes.length > 0
    ? uniqueTimes.sort((a, b) => toMinutes(a) - toMinutes(b))
    : DEFAULT_TIMES;

  const getSlot = (day: string, time: string) =>
    slots.find(s => s.day === day && s.time === time);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[500px]">
        <thead>
          <tr>
            <th className="text-left text-gray-400 font-medium pb-2 pr-3 w-20">
              {t('common.date') || 'Time'}
            </th>
            {displayDays.map(d => (
              <th key={d} className={`text-center font-semibold pb-2 px-1 ${
                highlightToday && d === todayName ? 'text-blue-600' : 'text-gray-600'
              }`}>
                <div>{t(DAY_T_KEY[d]) || DAY_FALLBACK[d]}</div>
                {highlightToday && d === todayName && (
                  <div className="text-[10px] text-blue-500 font-normal">
                    {t('day.today') || 'Today'}
                  </div>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {displayTimes.map(time => (
            <tr key={time}>
              <td className="text-gray-400 py-2 pr-3 whitespace-nowrap">{time}</td>
              {displayDays.map(day => {
                const slot = getSlot(day, time);
                return (
                  <td key={day} className="py-1.5 px-1">
                    {slot ? (
                      <div
                        className={`${slot.color} text-white rounded-md px-2 py-1 text-center leading-tight ${onSlotClick ? 'cursor-pointer hover:brightness-110 transition' : ''}`}
                        onClick={() => onSlotClick?.(slot)}
                        title={onSlotClick ? `Open ${slot.course}` : undefined}
                      >
                        <div className="font-semibold truncate">{slot.course}</div>
                        {slot.teacher && <div className="opacity-80 text-[10px]">{slot.teacher}</div>}
                      </div>
                    ) : (
                      <div className="h-8" />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/** Convert Course objects (with schedule field) into ScheduleSlot array.
 *  Includes ALL courses with a valid start_time — not filtered to preset time slots. */
const COURSE_COLORS = [
  'bg-orange-400', 'bg-emerald-500', 'bg-blue-500',
  'bg-purple-500', 'bg-rose-500', 'bg-teal-500', 'bg-yellow-500',
];

export function coursesToSlots(
  courses: Array<{ id?: string; name: string; schedule?: any; teacher_name?: string }>,
  teacherName?: string
): ScheduleSlot[] {
  const slots: ScheduleSlot[] = [];
  courses.forEach((c, idx) => {
    if (!c.schedule?.days || !c.schedule.start_time) return;
    const color = COURSE_COLORS[idx % COURSE_COLORS.length];
    const shortName = c.name.split('—')[0].trim().split(' ').slice(0, 2).join(' ');
    for (const day of c.schedule.days) {
      const time = formatTime(c.schedule.start_time);
      if (time) {
        slots.push({ id: c.id, day, time, course: shortName, teacher: c.teacher_name || teacherName, color });
      }
    }
  });
  return slots;
}

function formatTime(t?: string): string {
  if (!t) return '';
  const [h, m] = t.split(':').map(Number);
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hour   = h > 12 ? h - 12 : h || 12;
  return `${hour}:${String(m).padStart(2, '0')} ${suffix}`;
}
