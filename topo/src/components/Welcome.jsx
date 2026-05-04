import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mountain, ArrowRight, LogIn, Eye, EyeOff } from 'lucide-react';

function TopoBackground() {
  const lines = [
    "M-100,200 Q100,100 300,200 T700,200 T1100,200 T1500,200",
    "M-100,280 Q150,160 350,280 T750,280 T1150,280 T1550,280",
    "M-100,360 Q200,220 400,360 T800,360 T1200,360 T1600,360",
    "M-100,440 Q250,280 450,440 T850,440 T1250,440 T1650,440",
    "M-100,520 Q120,380 320,520 T720,520 T1120,520 T1520,520",
    "M-100,600 Q180,440 380,600 T780,600 T1180,600 T1580,600",
    "M-100,680 Q230,500 430,680 T830,680 T1230,680 T1630,680",
    "M-100,760 Q160,580 360,760 T760,760 T1160,760 T1560,760",
    "M-100,120 Q270,20 470,120 T870,120 T1270,120 T1670,120",
    "M-100,40 Q300,-60 500,40 T900,40 T1300,40 T1700,40",
  ];

  return (
    <div className="topo-bg">
      <svg className="topo-lines" viewBox="0 0 1400 800" preserveAspectRatio="none">
        {lines.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="#ff9100" strokeWidth="1.5" />
        ))}
      </svg>
    </div>
  );
}

export default function Welcome({ onSignUp, onLogin }) {
  const [mode, setMode] = useState('landing'); // landing | signup | login
  const [showPw, setShowPw] = useState(false);
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [errors, setErrors] = useState({});

  const validate = () => {
    const errs = {};
    if (mode === 'signup') {
      if (!form.username.trim()) errs.username = 'Username required';
      if (!form.email.includes('@')) errs.email = 'Valid email required';
    } else {
      if (!form.email.trim()) errs.email = 'Email required';
    }
    if (!form.password || form.password.length < 3) errs.password = 'Password required';
    return errs;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    const userData = {
      username: form.username || form.email.split('@')[0],
      email: form.email,
      avatarColor: '#ff9100',
      joinDate: new Date().toISOString(),
    };
    if (mode === 'signup') onSignUp(userData);
    else onLogin(userData);
  };

  return (
    <div className="relative w-full min-h-screen bg-slate-950 flex flex-col items-center justify-center overflow-hidden">
      <TopoBackground />

      {/* Radial gradient overlay */}
      <div className="absolute inset-0 bg-gradient-radial from-transparent via-slate-950/60 to-slate-950 z-0" 
        style={{ background: 'radial-gradient(ellipse at center, transparent 0%, rgba(2,6,23,0.5) 50%, rgba(2,6,23,0.95) 100%)' }} />

      <div className="relative z-10 w-full max-w-md px-6">
        <AnimatePresence mode="wait">
          {mode === 'landing' && (
            <motion.div key="landing" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.5 }} className="text-center">
              
              {/* Logo */}
              <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.2, duration: 0.6, type: 'spring' }} className="mb-6">
                <div className="flex items-center justify-center gap-3 mb-2">
                  <Mountain className="text-sar" size={40} strokeWidth={2.5} />
                  <span className="text-7xl font-black tracking-tighter" style={{ color: '#ff9100', fontFamily: 'system-ui' }}>
                    TOPO
                  </span>
                </div>
                <div className="h-0.5 w-24 bg-gradient-to-r from-transparent via-sar to-transparent mx-auto" />
              </motion.div>

              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
                className="text-slate-400 text-lg mb-3 tracking-wide">
                Your Trail. Your Network. Your Data.
              </motion.p>

              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
                className="text-slate-600 text-sm mb-12">
                Mesh-powered trail network for explorers
              </motion.p>

              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8 }} className="flex flex-col gap-4">
                <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                  onClick={() => setMode('signup')}
                  className="btn-sar w-full flex items-center justify-center gap-2 text-base py-4">
                  Get Started <ArrowRight size={18} />
                </motion.button>
                <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                  onClick={() => setMode('login')}
                  className="btn-outline w-full flex items-center justify-center gap-2 text-base py-4">
                  <LogIn size={18} /> Log In
                </motion.button>
              </motion.div>

              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }}
                className="text-slate-700 text-xs mt-10 tracking-widest uppercase">
                Offline-first · Mesh-ready · Private
              </motion.p>
            </motion.div>
          )}

          {(mode === 'signup' || mode === 'login') && (
            <motion.div key="form" initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
              
              <div className="flex items-center gap-3 mb-8">
                <Mountain className="text-sar" size={24} />
                <span className="text-3xl font-black text-sar tracking-tight">TOPO</span>
              </div>

              <h2 className="text-2xl font-bold text-white mb-2">
                {mode === 'signup' ? 'Create your account' : 'Welcome back'}
              </h2>
              <p className="text-slate-500 text-sm mb-8">
                {mode === 'signup' ? 'Join the trail network.' : 'Back on the trail.'}
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'signup' && (
                  <div>
                    <label className="text-xs text-slate-500 uppercase tracking-wider mb-1.5 block">Username</label>
                    <input
                      type="text"
                      placeholder="trailblazer_99"
                      value={form.username}
                      onChange={(e) => setForm({ ...form, username: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-sar transition-colors"
                    />
                    {errors.username && <p className="text-red-400 text-xs mt-1">{errors.username}</p>}
                  </div>
                )}
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wider mb-1.5 block">Email</label>
                  <input
                    type="email"
                    placeholder="you@trail.com"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-sar transition-colors"
                  />
                  {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wider mb-1.5 block">Password</label>
                  <div className="relative">
                    <input
                      type={showPw ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 pr-12 text-white placeholder-slate-600 focus:outline-none focus:border-sar transition-colors"
                    />
                    <button type="button" onClick={() => setShowPw(!showPw)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                      {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  {errors.password && <p className="text-red-400 text-xs mt-1">{errors.password}</p>}
                </div>

                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  type="submit"
                  className="btn-sar w-full mt-2 py-4 text-base">
                  {mode === 'signup' ? 'Create Account' : 'Sign In'}
                </motion.button>
              </form>

              <p className="text-slate-600 text-sm mt-6 text-center">
                {mode === 'signup' ? 'Already have an account?' : "Don't have an account?"}
                {' '}
                <button onClick={() => { setMode(mode === 'signup' ? 'login' : 'signup'); setErrors({}); }}
                  className="text-sar hover:text-sar-dark transition-colors font-semibold">
                  {mode === 'signup' ? 'Log in' : 'Sign up'}
                </button>
              </p>

              <button onClick={() => setMode('landing')}
                className="text-slate-600 text-xs mt-4 block mx-auto hover:text-slate-400 transition-colors">
                ← Back
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
