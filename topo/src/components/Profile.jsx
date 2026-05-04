import { motion } from 'framer-motion';
import { Mountain, MapPin, Calendar, Edit3, Award, Users, Activity } from 'lucide-react';

const stats = [
  { icon: Activity, label: 'Posts', value: '47' },
  { icon: Mountain, label: 'Trails', value: '183' },
  { icon: Users, label: 'Crew', value: '8' },
];

const badges = [
  { icon: '��️', label: 'Summit x10' },
  { icon: '📡', label: 'Mesh Pioneer' },
  { icon: '⛺', label: 'Overnight Pro' },
  { icon: '🗺️', label: 'Navigator' },
  { icon: '🩺', label: 'First Aid' },
  { icon: '❄️', label: 'Winter Ready' },
];

export default function Profile({ user, themeColor }) {
  const username = user?.username || 'explorer';
  const joinDate = user?.joinDate ? new Date(user.joinDate).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'May 2025';

  return (
    <div className="pb-8">
      {/* Hero banner */}
      <div className="relative h-32 overflow-hidden"
        style={{ background: `linear-gradient(135deg, ${themeColor}30, #1e293b)` }}>
        <div className="absolute inset-0 opacity-10">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="absolute border rounded-full"
              style={{
                width: `${(i + 1) * 80}px`, height: `${(i + 1) * 80}px`,
                borderColor: themeColor,
                top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
              }} />
          ))}
        </div>
      </div>

      <div className="px-4">
        {/* Avatar */}
        <div className="flex items-end justify-between -mt-8 mb-4">
          <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            className="w-20 h-20 rounded-full border-4 border-slate-950 flex items-center justify-center font-black text-3xl text-black"
            style={{ backgroundColor: themeColor }}>
            {username[0].toUpperCase()}
          </motion.div>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-700 text-slate-300 text-sm font-semibold hover:border-slate-500 transition-colors">
            <Edit3 size={14} /> Edit
          </motion.button>
        </div>

        {/* Name */}
        <div className="mb-4">
          <h2 className="text-2xl font-black text-white">@{username}</h2>
          <p className="text-slate-500 text-sm">{user?.email || 'trail@topo.io'}</p>
          <div className="flex items-center gap-3 mt-2">
            <div className="flex items-center gap-1 text-slate-500 text-xs">
              <MapPin size={12} />
              <span>Summit Ridge, CA</span>
            </div>
            <div className="flex items-center gap-1 text-slate-500 text-xs">
              <Calendar size={12} />
              <span>Joined {joinDate}</span>
            </div>
          </div>
          <p className="text-slate-400 text-sm mt-2">Explorer. Trail runner. Mesh radio enthusiast. Always above treeline. 🏔️</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="topo-card p-4 text-center">
                <Icon size={18} style={{ color: themeColor }} className="mx-auto mb-2" />
                <p className="text-2xl font-black text-white">{stat.value}</p>
                <p className="text-slate-500 text-xs">{stat.label}</p>
              </motion.div>
            );
          })}
        </div>

        {/* Badges */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Award size={16} style={{ color: themeColor }} />
            <h3 className="text-xs text-slate-500 uppercase tracking-widest font-semibold">Trail Badges</h3>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {badges.map((badge, i) => (
              <motion.div key={badge.label} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
                className="topo-card p-3 flex flex-col items-center gap-1.5">
                <span className="text-2xl">{badge.icon}</span>
                <span className="text-xs text-slate-400 text-center leading-tight">{badge.label}</span>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Preset tag */}
        <div className="topo-card p-4 flex items-center gap-3">
          <div className="p-2 rounded-xl" style={{ backgroundColor: `${themeColor}15` }}>
            <Mountain size={18} style={{ color: themeColor }} />
          </div>
          <div>
            <p className="text-white font-semibold text-sm">TOPO Explorer Preset</p>
            <p className="text-slate-500 text-xs">Mesh Tier: Pioneer · 5 nodes connected</p>
          </div>
          <div className="ml-auto">
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: themeColor }} />
          </div>
        </div>
      </div>
    </div>
  );
}
