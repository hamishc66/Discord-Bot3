import { motion } from 'framer-motion';
import { Users, MapPin, Clock, Radio } from 'lucide-react';
import { mockCrew } from '../mockDatabase';

const STATUS_COLORS = {
  active: '#22c55e',
  idle: '#f59e0b',
  offline: '#475569',
};

export default function CrewView({ themeColor }) {
  return (
    <div className="pb-4">
      <div className="px-4 pt-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-black text-white">Your Crew</h2>
            <p className="text-slate-500 text-xs">
              {mockCrew.filter((u) => u.status === 'active').length} active ·{' '}
              {mockCrew.filter((u) => u.status === 'idle').length} idle
            </p>
          </div>
          <div className="glass px-3 py-1.5 rounded-full flex items-center gap-1.5">
            <Radio size={12} style={{ color: themeColor }} />
            <span className="text-xs" style={{ color: themeColor }}>Mesh On</span>
          </div>
        </div>

        <div className="space-y-3">
          {mockCrew.map((member, i) => (
            <motion.div key={member.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
              className="topo-card p-4 flex items-center gap-3">
              <div className="relative flex-shrink-0">
                <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-black"
                  style={{ backgroundColor: member.avatarColor }}>
                  {member.username[0].toUpperCase()}
                </div>
                <div className="absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-900"
                  style={{ backgroundColor: STATUS_COLORS[member.status] }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm">@{member.username}</p>
                <div className="flex items-center gap-3 mt-1">
                  <div className="flex items-center gap-1 text-slate-500 text-xs">
                    <MapPin size={10} />
                    <span>{member.distanceKm} km away</span>
                  </div>
                  <div className="flex items-center gap-1 text-slate-500 text-xs">
                    <Clock size={10} />
                    <span>{member.lastActive}</span>
                  </div>
                </div>
                <p className="text-slate-600 text-xs mt-0.5 truncate">{member.trail}</p>
              </div>
              <div>
                <span className="text-xs px-2 py-1 rounded-lg capitalize font-medium"
                  style={{ color: STATUS_COLORS[member.status], backgroundColor: `${STATUS_COLORS[member.status]}15` }}>
                  {member.status}
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
