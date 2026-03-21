import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/* ─── Inline SVG Logo ─────────────────────────────────────────────────────── */
const IQPlusLogo: React.FC<{ size?: number }> = ({ size = 36 }) => (
  <svg width={size * 3.2} height={size} viewBox="0 0 160 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Pencil icon */}
    <rect x="2" y="30" width="18" height="5" rx="1" fill="#f97316" transform="rotate(-35 11 32)" />
    <polygon points="2,38 6,44 10,38" fill="#f97316" />
    {/* iQ letters */}
    <text x="22" y="36" fontFamily="Arial" fontWeight="900" fontSize="28" fill="#1e3a5f">i</text>
    <text x="32" y="36" fontFamily="Arial" fontWeight="900" fontSize="28" fill="#2563eb">Q</text>
    {/* plus+ */}
    <text x="62" y="36" fontFamily="Arial" fontWeight="700" fontSize="26" fill="#1e3a5f">plus</text>
    <text x="118" y="22" fontFamily="Arial" fontWeight="900" fontSize="18" fill="#2563eb">+</text>
  </svg>
);

/* ─── Hero Illustration (SVG) ─────────────────────────────────────────────── */
const HeroIllustration: React.FC = () => (
  <svg viewBox="0 0 520 420" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full max-w-lg">
    {/* Background arc */}
    <ellipse cx="290" cy="380" rx="210" ry="40" fill="#dbeafe" opacity="0.6" />

    {/* Laptop */}
    <rect x="155" y="235" width="180" height="110" rx="8" fill="#1e40af" />
    <rect x="163" y="243" width="164" height="94" rx="4" fill="#eff6ff" />
    <rect x="130" y="345" width="230" height="10" rx="5" fill="#93c5fd" />
    {/* Screen content lines */}
    <rect x="175" y="260" width="80" height="6" rx="3" fill="#bfdbfe" />
    <rect x="175" y="274" width="120" height="6" rx="3" fill="#bfdbfe" />
    <rect x="175" y="288" width="100" height="6" rx="3" fill="#bfdbfe" />
    {/* Bar chart on screen */}
    <rect x="260" y="300" width="14" height="28" rx="2" fill="#3b82f6" />
    <rect x="278" y="285" width="14" height="43" rx="2" fill="#2563eb" />
    <rect x="296" y="293" width="14" height="35" rx="2" fill="#60a5fa" />

    {/* Adult figure (teacher) */}
    {/* Body */}
    <rect x="98" y="195" width="42" height="65" rx="10" fill="#2563eb" />
    {/* Head */}
    <circle cx="119" cy="178" r="22" fill="#fed7aa" />
    {/* Hair */}
    <path d="M97 170 Q119 148 141 170" fill="#1e3a5f" />
    {/* Legs */}
    <rect x="103" y="255" width="14" height="48" rx="6" fill="#1e40af" />
    <rect x="122" y="255" width="14" height="48" rx="6" fill="#1e40af" />
    {/* Shoes */}
    <ellipse cx="110" cy="303" rx="10" ry="5" fill="#1e3a5f" />
    <ellipse cx="129" cy="303" rx="10" ry="5" fill="#1e3a5f" />
    {/* Arm pointing */}
    <line x1="140" y1="215" x2="165" y2="200" stroke="#fed7aa" strokeWidth="10" strokeLinecap="round" />

    {/* Child 1 (left) */}
    <circle cx="62" cy="245" r="16" fill="#fde68a" />
    <path d="M46 238 Q62 224 78 238" fill="#92400e" />
    <rect x="50" y="258" width="24" height="46" rx="8" fill="#f97316" />
    <rect x="53" y="300" width="9" height="36" rx="4" fill="#f97316" />
    <rect x="64" y="300" width="9" height="36" rx="4" fill="#f97316" />
    <ellipse cx="57" cy="336" rx="7" ry="4" fill="#1e3a5f" />
    <ellipse cx="68" cy="336" rx="7" ry="4" fill="#1e3a5f" />
    {/* Book in child's hand */}
    <rect x="30" y="268" width="22" height="28" rx="3" fill="#10b981" />
    <line x1="41" y1="268" x2="41" y2="296" stroke="white" strokeWidth="1.5" />

    {/* Child 2 (right) */}
    <circle cx="370" cy="248" r="16" fill="#fed7aa" />
    <path d="M354 241 Q370 226 386 241" fill="#1e3a5f" />
    <rect x="358" y="261" width="24" height="46" rx="8" fill="#7c3aed" />
    <rect x="361" y="303" width="9" height="36" rx="4" fill="#7c3aed" />
    <rect x="372" y="303" width="9" height="36" rx="4" fill="#7c3aed" />
    <ellipse cx="365" cy="339" rx="7" ry="4" fill="#1e3a5f" />
    <ellipse cx="376" cy="339" rx="7" ry="4" fill="#1e3a5f" />
    {/* Backpack on child 2 */}
    <rect x="382" y="265" width="18" height="28" rx="4" fill="#6d28d9" />
    <rect x="385" y="270" width="12" height="10" rx="2" fill="#5b21b6" />

    {/* Floating icon: Calendar (top right) */}
    <circle cx="440" cy="80" r="32" fill="#2563eb" opacity="0.15" />
    <circle cx="440" cy="80" r="28" fill="#2563eb" />
    <rect x="424" y="72" width="32" height="24" rx="3" fill="white" opacity="0.9" />
    <rect x="424" y="64" width="32" height="12" rx="3" fill="#1d4ed8" />
    <rect x="430" y="60" width="4" height="8" rx="2" fill="white" />
    <rect x="446" y="60" width="4" height="8" rx="2" fill="white" />
    <rect x="428" y="78" width="5" height="5" rx="1" fill="#2563eb" />
    <rect x="437" y="78" width="5" height="5" rx="1" fill="#2563eb" />
    <rect x="446" y="78" width="5" height="5" rx="1" fill="#2563eb" />
    <rect x="428" y="87" width="5" height="5" rx="1" fill="#2563eb" />
    <rect x="437" y="87" width="5" height="5" rx="1" fill="#2563eb" />

    {/* Floating icon: Clock (right middle) */}
    <circle cx="470" cy="195" r="26" fill="white" />
    <circle cx="470" cy="195" r="22" stroke="#e2e8f0" strokeWidth="3" fill="white" />
    <circle cx="470" cy="195" r="3" fill="#2563eb" />
    <line x1="470" y1="195" x2="470" y2="179" stroke="#1e40af" strokeWidth="3" strokeLinecap="round" />
    <line x1="470" y1="195" x2="480" y2="200" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" />

    {/* Floating icon: Gear (top left of illustration) */}
    <circle cx="68" cy="145" r="24" fill="#0d9488" opacity="0.15" />
    <circle cx="68" cy="145" r="20" fill="#0d9488" />
    <circle cx="68" cy="145" r="8" fill="white" />
    <rect x="65" y="125" width="6" height="10" rx="3" fill="white" />
    <rect x="65" y="155" width="6" height="10" rx="3" fill="white" />
    <rect x="48" y="142" width="10" height="6" rx="3" fill="white" />
    <rect x="78" y="142" width="10" height="6" rx="3" fill="white" />

    {/* Floating icon: Chart bar (left) */}
    <circle cx="28" cy="175" r="24" fill="#f97316" opacity="0.15" />
    <circle cx="28" cy="175" r="20" fill="#f97316" />
    <rect x="18" y="178" width="6" height="10" rx="1" fill="white" />
    <rect x="26" y="170" width="6" height="18" rx="1" fill="white" />
    <rect x="34" y="174" width="6" height="14" rx="1" fill="white" />
    <line x1="16" y1="189" x2="42" y2="189" stroke="white" strokeWidth="1.5" />

    {/* Dashed arc lines (decorative) */}
    <path d="M210 120 Q310 80 390 140" stroke="#bfdbfe" strokeWidth="2" strokeDasharray="6 4" fill="none" />
    <path d="M180 150 Q240 110 320 130" stroke="#bfdbfe" strokeWidth="2" strokeDasharray="6 4" fill="none" />
  </svg>
);

/* ─── Login Illustration ──────────────────────────────────────────────────── */
export const LoginIllustration: React.FC = () => (
  <svg viewBox="0 0 400 380" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full max-w-sm">
    <ellipse cx="200" cy="355" rx="160" ry="25" fill="#dbeafe" opacity="0.7" />
    {/* Desk */}
    <rect x="60" y="265" width="280" height="14" rx="4" fill="#bfdbfe" />
    <rect x="100" y="279" width="12" height="70" rx="4" fill="#93c5fd" />
    <rect x="288" y="279" width="12" height="70" rx="4" fill="#93c5fd" />
    {/* Laptop */}
    <rect x="120" y="180" width="155" height="88" rx="6" fill="#1e40af" />
    <rect x="127" y="187" width="141" height="74" rx="3" fill="#eff6ff" />
    <rect x="100" y="266" width="200" height="10" rx="4" fill="#93c5fd" />
    {/* Screen: dashboard lines */}
    <rect x="135" y="198" width="60" height="5" rx="2" fill="#bfdbfe" />
    <rect x="135" y="210" width="90" height="4" rx="2" fill="#bfdbfe" />
    <rect x="135" y="220" width="75" height="4" rx="2" fill="#bfdbfe" />
    {/* Mini chart */}
    <rect x="210" y="222" width="10" height="22" rx="1" fill="#3b82f6" />
    <rect x="223" y="214" width="10" height="30" rx="1" fill="#2563eb" />
    <rect x="236" y="218" width="10" height="26" rx="1" fill="#60a5fa" />
    {/* Person */}
    <circle cx="200" cy="125" r="38" fill="#fed7aa" />
    <path d="M162 112 Q200 82 238 112" fill="#92400e" />
    <rect x="165" y="160" width="70" height="72" rx="14" fill="#3b82f6" />
    {/* Floating elements */}
    <circle cx="340" cy="100" r="24" fill="#2563eb" opacity="0.12" />
    <circle cx="340" cy="100" r="18" fill="#2563eb" />
    <path d="M331 100 L337 106 L350 93" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    <circle cx="55" cy="170" r="20" fill="#0d9488" opacity="0.12" />
    <circle cx="55" cy="170" r="15" fill="#0d9488" />
    <path d="M48 170 Q55 162 62 170" stroke="white" strokeWidth="2" fill="none" />
    <circle cx="55" cy="175" r="2" fill="white" />
    {/* Dashes */}
    <path d="M80 200 Q150 150 230 160" stroke="#bfdbfe" strokeWidth="1.5" strokeDasharray="5 4" fill="none" />
    <path d="M290 130 Q330 160 350 200" stroke="#bfdbfe" strokeWidth="1.5" strokeDasharray="5 4" fill="none" />
  </svg>
);

/* ─── Signup Illustration ─────────────────────────────────────────────────── */
export const SignupIllustration: React.FC = () => (
  <svg viewBox="0 0 400 380" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full max-w-sm">
    <ellipse cx="200" cy="355" rx="160" ry="25" fill="#dbeafe" opacity="0.7" />
    {/* Desk */}
    <rect x="60" y="265" width="280" height="14" rx="4" fill="#bfdbfe" />
    <rect x="100" y="279" width="12" height="70" rx="4" fill="#93c5fd" />
    <rect x="288" y="279" width="12" height="70" rx="4" fill="#93c5fd" />
    {/* Laptop */}
    <rect x="120" y="180" width="155" height="88" rx="6" fill="#7c3aed" />
    <rect x="127" y="187" width="141" height="74" rx="3" fill="#eff6ff" />
    <rect x="100" y="266" width="200" height="10" rx="4" fill="#93c5fd" />
    {/* Screen: rocket + stars */}
    <path d="M185 240 L195 210 L205 240 Z" fill="#6d28d9" />
    <ellipse cx="195" cy="243" rx="8" ry="5" fill="#f97316" opacity="0.7" />
    <circle cx="175" cy="220" r="3" fill="#fde68a" />
    <circle cx="218" cy="215" r="4" fill="#fde68a" />
    <circle cx="210" cy="232" r="2" fill="#fde68a" />
    {/* Person (yellow hair) */}
    <circle cx="200" cy="122" r="38" fill="#fed7aa" />
    <path d="M163 114 Q185 86 220 108 L238 114" fill="#fbbf24" />
    <rect x="168" y="157" width="64" height="70" rx="14" fill="#7c3aed" />
    {/* Floating elements */}
    <circle cx="340" cy="110" r="24" fill="#f97316" opacity="0.12" />
    <circle cx="340" cy="110" r="18" fill="#f97316" />
    <path d="M334 110 L340 116 L353 103" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    <circle cx="55" cy="165" r="20" fill="#2563eb" opacity="0.12" />
    <circle cx="55" cy="165" r="15" fill="#2563eb" />
    <rect x="49" y="162" width="12" height="6" rx="2" fill="white" />
    <rect x="52" y="158" width="6" height="14" rx="2" fill="white" />
    {/* Dashes */}
    <path d="M85 190 Q150 145 235 158" stroke="#bfdbfe" strokeWidth="1.5" strokeDasharray="5 4" fill="none" />
    <path d="M295 125 Q330 155 348 195" stroke="#bfdbfe" strokeWidth="1.5" strokeDasharray="5 4" fill="none" />
  </svg>
);

/* ─── Shared page chrome ──────────────────────────────────────────────────── */
export const PageShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const dashRoute = {
    admin: '/dashboard/admin', teacher: '/dashboard/teacher',
    student: '/dashboard/student', parent: '/dashboard/parent',
  }[user?.role || ''] || '/';

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(155deg, #eff6ff 0%, #e0f2fe 40%, #f0fdf4 100%)' }}>
      {/* Top nav */}
      <nav className="flex items-center justify-between px-8 py-4">
        <Link to="/" className="flex items-center">
          <IQPlusLogo />
        </Link>
        <div className="flex items-center gap-3">
          {user ? (
            <button onClick={() => navigate(dashRoute)}
              className="bg-blue-600 text-white px-5 py-2 rounded-full text-sm font-semibold hover:bg-blue-700 transition">
              Dashboard
            </button>
          ) : (
            <>
              <Link to="/login"
                className="flex items-center gap-2 border border-blue-300 text-blue-700 px-5 py-2 rounded-full text-sm font-semibold hover:bg-blue-50 transition">
                <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
                Login
              </Link>
              <Link to="/signup"
                className="bg-blue-600 text-white px-5 py-2 rounded-full text-sm font-semibold hover:bg-blue-700 transition">
                Sign Up
              </Link>
            </>
          )}
        </div>
      </nav>
      {children}
    </div>
  );
};

/* ─── Landing Page ────────────────────────────────────────────────────────── */
export const LandingPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleGetStarted = () => {
    if (user) {
      const dashRoute = {
        admin: '/dashboard/admin', teacher: '/dashboard/teacher',
        student: '/dashboard/student', parent: '/dashboard/parent',
      }[user.role || ''] || '/dashboard/student';
      navigate(dashRoute);
    } else {
      navigate('/signup');
    }
  };

  return (
    <PageShell>
      <div className="max-w-6xl mx-auto px-8 pt-10 pb-20 flex flex-col md:flex-row items-center gap-12">
        {/* Left: text */}
        <div className="flex-1 max-w-lg">
          <h1 className="text-5xl font-black text-gray-900 leading-tight mb-5">
            Welcome to{' '}
            <span className="text-blue-600">IQ PLUS</span>
          </h1>
          <p className="text-gray-500 text-lg leading-relaxed mb-8">
            Smart Learning Management System<br />
            For Personalized Academic Support.
          </p>
          <button
            onClick={handleGetStarted}
            className="bg-blue-600 hover:bg-blue-700 text-white px-9 py-3.5 rounded-xl text-base font-semibold shadow-lg shadow-blue-200 transition"
          >
            Get Started
          </button>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-3 mt-10">
            {['Role-Based Dashboards', 'AI Learning Insights', 'Progress Tracking', 'Course Management'].map(f => (
              <span key={f} className="bg-white text-blue-700 text-xs font-semibold px-3 py-1.5 rounded-full shadow-sm border border-blue-100">
                {f}
              </span>
            ))}
          </div>
        </div>

        {/* Right: illustration */}
        <div className="flex-1 flex justify-center">
          <HeroIllustration />
        </div>
      </div>
    </PageShell>
  );
};
