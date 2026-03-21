import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { PageShell, SignupIllustration } from './LandingPage';

type Role = 'TEACHER' | 'STUDENT' | 'PARENT';

interface FormData {
  firstName: string; lastName: string;
  email: string; phone: string;
  password: string; confirmPassword: string;
  subject?: string; employeeId?: string;
  grade?: string; dob?: string; parentContact?: string;
  childName?: string; childGrade?: string; relationship?: string;
}

const GRADES = [
  'Grade 1','Grade 2','Grade 3','Grade 4','Grade 5','Grade 6',
  'Grade 7','Grade 8','Grade 9','Grade 10','Grade 11','Grade 12',
];

const ROLES: { id: Role; label: string; icon: string; desc: string }[] = [
  { id: 'TEACHER', label: 'Teacher',  icon: '🎓', desc: 'Manage classes & student progress' },
  { id: 'STUDENT', label: 'Student',  icon: '📚', desc: 'Access courses, grades & materials' },
  { id: 'PARENT',  label: 'Parent',   icon: '👨‍👩‍👧', desc: "Monitor your child's performance" },
];

const F = 'w-full px-4 py-3 border border-gray-200 rounded-xl bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder:text-gray-300 shadow-sm';
const L = 'block text-sm font-semibold text-gray-700 mb-1.5';

export const SignupPage: React.FC = () => {
  const [step, setStep]       = useState<1 | 2>(1);
  const [role, setRole]       = useState<Role | null>(null);
  const [agreed, setAgreed]   = useState(false);
  const [form, setForm]       = useState<FormData>({
    firstName: '', lastName: '', email: '', phone: '', password: '', confirmPassword: '',
  });
  const [showPw, setShowPw]           = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [error, setError]             = useState('');
  const [loading, setLoading]         = useState(false);
  const [pendingApproval, setPendingApproval] = useState(false);
  const { signup } = useAuth();
  const navigate   = useNavigate();

  const set = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirmPassword) { setError('Passwords do not match.'); return; }
    if (!agreed) { setError('Please agree to the Terms and Privacy Policy.'); return; }
    setLoading(true);
    try {
      await signup({ ...form, role: role! });
      navigate('/');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Registration failed.';
      if (msg.startsWith('PENDING:')) {
        setPendingApproval(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  if (pendingApproval) {
    return (
      <PageShell>
        <div className="max-w-xl mx-auto px-8 pt-16 pb-20 text-center">
          <div className="text-5xl mb-4">⏳</div>
          <h2 className="text-2xl font-black text-gray-900 mb-3">Registration Submitted</h2>
          <p className="text-gray-500 text-sm mb-6">
            Your account is pending admin approval. You will be able to log in once an administrator reviews your registration.
          </p>
          <Link to="/login" className="text-blue-600 font-semibold hover:underline text-sm">
            Back to Login ›
          </Link>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <div className="max-w-5xl mx-auto px-8 pt-6 pb-20 flex flex-col md:flex-row items-start gap-12">

        {/* Left: Form */}
        <div className="flex-1 max-w-md w-full">
          <h2 className="text-3xl font-black text-gray-900 mb-6">Sign Up</h2>

          {/* Step 1: Role picker */}
          {step === 1 && (
            <>
              <p className="text-gray-500 text-sm mb-4">I am a…</p>
              <div className="space-y-3 mb-6">
                {ROLES.map(r => (
                  <button key={r.id} type="button"
                    onClick={() => { setRole(r.id); setStep(2); }}
                    className="w-full flex items-center gap-4 px-4 py-3.5 border-2 border-gray-200 rounded-xl bg-white hover:border-blue-400 hover:bg-blue-50 transition text-left">
                    <span className="text-2xl">{r.icon}</span>
                    <div>
                      <p className="font-bold text-gray-800 text-sm">{r.label}</p>
                      <p className="text-gray-400 text-xs">{r.desc}</p>
                    </div>
                  </button>
                ))}
              </div>
              <p className="text-sm text-gray-500">
                Already have an account?{' '}
                <Link to="/login" className="text-blue-600 font-semibold hover:underline">Login</Link>
              </p>
            </>
          )}

          {/* Step 2: Registration form */}
          {step === 2 && role && (
            <>
              <button onClick={() => { setStep(1); setError(''); }}
                className="flex items-center gap-1 text-blue-600 text-sm font-semibold mb-4 hover:underline">
                ← Back
              </button>

              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 rounded-xl text-sm">{error}</div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Name */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={L}>First Name</label>
                    <input name="firstName" placeholder="John" onChange={set} required className={F} />
                  </div>
                  <div>
                    <label className={L}>Last Name</label>
                    <input name="lastName" placeholder="Doe" onChange={set} required className={F} />
                  </div>
                </div>

                <div>
                  <label className={L}>Email</label>
                  <input name="email" type="email" placeholder="hello@example.com" onChange={set} required className={F} />
                </div>

                <div>
                  <label className={L}>Phone Number</label>
                  <input name="phone" type="tel" placeholder="+1 234 567 8900" onChange={set} required className={F} />
                </div>

                {/* Teacher extra fields */}
                {role === 'TEACHER' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={L}>Subject</label>
                      <input name="subject" placeholder="e.g. Mathematics" onChange={set} required className={F} />
                    </div>
                    <div>
                      <label className={L}>Employee ID <span className="text-gray-400 font-normal">(opt)</span></label>
                      <input name="employeeId" placeholder="TCH-001" onChange={set} className={F} />
                    </div>
                  </div>
                )}

                {/* Student extra fields */}
                {role === 'STUDENT' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className={L}>Grade <span className="text-gray-400 font-normal">(opt)</span></label>
                        <select name="grade" onChange={set} defaultValue="" className={F}>
                          <option value="">Skip for now</option>
                          {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className={L}>Date of Birth <span className="text-gray-400 font-normal">(opt)</span></label>
                        <input name="dob" type="date" onChange={set} className={F} />
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
                      ℹ️ You can join courses after signing up — no course assignment is needed during registration.
                    </p>
                  </div>
                )}

                {/* Parent extra fields */}
                {role === 'PARENT' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className={L}>Child's Name <span className="text-gray-400 font-normal">(opt)</span></label>
                        <input name="childName" placeholder="Child's name" onChange={set} className={F} />
                      </div>
                      <div>
                        <label className={L}>Child's Grade <span className="text-gray-400 font-normal">(opt)</span></label>
                        <select name="childGrade" onChange={set} defaultValue="" className={F}>
                          <option value="">Skip for now</option>
                          {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
                      ℹ️ You don't need to assign a child now. After signing up, contact your school administrator to link your child's account.
                    </p>
                  </div>
                )}

                {/* Passwords */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={L}>Password</label>
                    <div className="relative">
                      <input name="password" type={showPw ? 'text' : 'password'} placeholder="Min 8 chars" onChange={set} required minLength={8} className={`${F} pr-10`} />
                      <button type="button" tabIndex={-1} onClick={() => setShowPw(v => !v)} aria-label={showPw ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        {showPw ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        )}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className={L}>Confirm Password</label>
                    <div className="relative">
                      <input name="confirmPassword" type={showConfirmPw ? 'text' : 'password'} placeholder="Repeat" onChange={set} required minLength={8} className={`${F} pr-10`} />
                      <button type="button" tabIndex={-1} onClick={() => setShowConfirmPw(v => !v)} aria-label={showConfirmPw ? 'Hide password' : 'Show password'} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        {showConfirmPw ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Terms */}
                <div className="flex items-center gap-2">
                  <input id="terms" type="checkbox" checked={agreed} onChange={e => setAgreed(e.target.checked)}
                    className="w-4 h-4 accent-blue-600" />
                  <label htmlFor="terms" className="text-sm text-gray-500 cursor-pointer">
                    I agree to the{' '}
                    <span className="text-blue-600">Terms</span>{' '}and{' '}
                    <span className="text-blue-600">Privacy Policy</span>
                  </label>
                </div>

                <button type="submit" disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-bold py-3 rounded-xl transition shadow-md shadow-blue-200">
                  {loading ? 'Creating account...' : 'Sign Up'}
                </button>
              </form>

              <p className="text-sm text-gray-500 mt-4">
                Already have an account?{' '}
                <Link to="/login" className="text-blue-600 font-semibold hover:underline">Login</Link>
              </p>
            </>
          )}
        </div>

        {/* Right: Illustration */}
        <div className="flex-1 flex justify-center items-start pt-8">
          <SignupIllustration />
        </div>
      </div>
    </PageShell>
  );
};
