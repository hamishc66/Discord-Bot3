import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertTriangle, XCircle, Plus, Package, X } from 'lucide-react';
import { mockGear } from '../mockDatabase';

const STATUS_CONFIG = {
  good: { icon: CheckCircle, color: '#22c55e', label: 'Good', bg: '#22c55e15' },
  check: { icon: AlertTriangle, color: '#f59e0b', label: 'Check', bg: '#f59e0b15' },
  flagged: { icon: XCircle, color: '#ef4444', label: 'Flagged', bg: '#ef444415' },
};

function AddGearModal({ onClose, onAdd, themeColor }) {
  const [form, setForm] = useState({ name: '', type: '', weightKg: '', brand: '' });
  const handleSubmit = () => {
    if (!form.name.trim()) return;
    onAdd({ ...form, weightKg: parseFloat(form.weightKg) || 0, safetyStatus: 'good', lastChecked: new Date().toISOString().split('T')[0], id: Date.now() });
    onClose();
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end">
      <motion.div initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="w-full bg-slate-900 border-t border-slate-800 rounded-t-3xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-white">Add Gear</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={20} /></button>
        </div>
        <div className="space-y-3">
          {[['name', 'Item Name'], ['brand', 'Brand'], ['type', 'Type (Pack, Shelter...)'], ['weightKg', 'Weight (kg)']].map(([key, label]) => (
            <div key={key}>
              <label className="text-xs text-slate-500 uppercase tracking-wider mb-1 block">{label}</label>
              <input type={key === 'weightKg' ? 'number' : 'text'}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-sar text-sm"
              />
            </div>
          ))}
        </div>
        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
          onClick={handleSubmit}
          className="w-full mt-4 py-3 rounded-xl font-bold text-black"
          style={{ backgroundColor: themeColor }}>
          Add to Locker
        </motion.button>
      </motion.div>
    </motion.div>
  );
}

export default function GearLocker({ themeColor }) {
  const [gear, setGear] = useState(mockGear);
  const [showModal, setShowModal] = useState(false);
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all' ? gear : gear.filter((g) => g.safetyStatus === filter);

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-black text-white">Gear Locker</h2>
            <p className="text-slate-500 text-xs">{gear.length} items · {gear.reduce((s, g) => s + (g.weightKg || 0), 0).toFixed(1)}kg total</p>
          </div>
          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-black text-sm"
            style={{ backgroundColor: themeColor }}>
            <Plus size={16} /> Add
          </motion.button>
        </div>

        {/* Filter pills */}
        <div className="flex gap-2">
          {['all', 'good', 'check', 'flagged'].map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all capitalize ${
                filter === f ? 'text-black' : 'bg-slate-900 border border-slate-800 text-slate-500'
              }`}
              style={filter === f ? { backgroundColor: themeColor } : {}}>
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 space-y-2">
        {filtered.map((item, i) => {
          const status = STATUS_CONFIG[item.safetyStatus] || STATUS_CONFIG.good;
          const StatusIcon = status.icon;
          return (
            <motion.div key={item.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="topo-card p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: `${themeColor}15` }}>
                <Package size={18} style={{ color: themeColor }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-semibold text-sm truncate">{item.name}</p>
                <p className="text-slate-500 text-xs">{item.brand} · {item.type} · {item.weightKg}kg</p>
                <p className="text-slate-600 text-xs">Checked: {item.lastChecked}</p>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl flex-shrink-0"
                style={{ backgroundColor: status.bg }}>
                <StatusIcon size={14} style={{ color: status.color }} />
                <span className="text-xs font-semibold" style={{ color: status.color }}>{status.label}</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {showModal && (
          <AddGearModal onClose={() => setShowModal(false)}
            onAdd={(item) => setGear([item, ...gear])} themeColor={themeColor} />
        )}
      </AnimatePresence>
    </div>
  );
}
