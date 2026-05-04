import { useState } from 'react';
import { motion } from 'framer-motion';
import { Compass, Mountain, Activity, Shield, Minus, Sliders,
  House, LayoutDashboard, Map, Radio, Package, Cloud, Users, User, ChevronRight } from 'lucide-react';

const PRESETS = [
  { id: 'explorer', label: 'Explorer', icon: Compass, accent: '#3b82f6', desc: 'Built for discovery' },
  { id: 'climber', label: 'Climber', icon: Mountain, accent: '#ff9100', desc: 'Vertical pursuits' },
  { id: 'runner', label: 'Runner', icon: Activity, accent: '#22c55e', desc: 'Fast & light' },
  { id: 'ranger', label: 'Ranger', icon: Shield, accent: '#ef4444', desc: 'Duty & terrain' },
  { id: 'minimal', label: 'Minimal', icon: Minus, accent: '#f1f5f9', desc: 'Clean & simple' },
  { id: 'custom', label: 'Custom', icon: Sliders, accent: '#a855f7', desc: 'Your rules' },
];

const TOOLBAR_ITEMS = [
  { id: 'home', label: 'Home', icon: House },
  { id: 'feed', label: 'Feed', icon: LayoutDashboard },
  { id: 'map', label: 'Map', icon: Map },
  { id: 'mesh', label: 'Mesh', icon: Radio },
  { id: 'gear', label: 'Gear', icon: Package },
  { id: 'weather', label: 'Weather', icon: Cloud },
  { id: 'crew', label: 'Crew', icon: Users },
  { id: 'profile', label: 'Profile', icon: User },
];

const THEME_COLORS = [
  { id: 'orange', label: 'SAR Orange', value: '#ff9100' },
  { id: 'blue', label: 'Alpine Blue', value: '#3b82f6' },
  { id: 'green', label: 'Trail Green', value: '#22c55e' },
  { id: 'red', label: 'Danger Red', value: '#ef4444' },
  { id: 'purple', label: 'Summit Purple', value: '#a855f7' },
  { id: 'white', label: 'Snow White', value: '#f1f5f9' },
];

export default function Customise({ user, onDone }) {
  const [preset, setPreset] = useState('explorer');
  const [selectedItems, setSelectedItems] = useState(['home', 'feed', 'map', 'mesh', 'profile']);
  const [themeColor, setThemeColor] = useState('#ff9100');

  const toggleItem = (id) => {
    if (selectedItems.includes(id)) {
      if (selectedItems.length > 1) setSelectedItems(selectedItems.filter((i) => i !== id));
    } else {
      if (selectedItems.length < 5) setSelectedItems([...selectedItems, id]);
    }
  };

  const handleDone = () => {
    onDone({ preset, toolbar: selectedItems, themeColor });
  };

  const selectedPreset = PRESETS.find((p) => p.id === preset);

  return (
    <div className="w-full min-h-screen bg-slate-950 overflow-y-auto">
      <div className="max-w-lg mx-auto px-5 py-8 pb-24">

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <p className="text-slate-500 text-sm mb-1">Hey {user?.username || 'trailblazer'} 👋</p>
          <h1 className="text-3xl font-black text-white">Make it yours</h1>
          <p className="text-slate-500 text-sm mt-1">Personalise your TOPO experience</p>
        </motion.div>

        {/* Section 1: Presets */}
        <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="mb-8">
          <h2 className="text-xs text-slate-500 uppercase tracking-widest mb-3 font-semibold">Choose a Preset</h2>
          <div className="grid grid-cols-3 gap-3">
            {PRESETS.map((p) => {
              const Icon = p.icon;
              const isActive = preset === p.id;
              return (
                <motion.button key={p.id} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
                  onClick={() => setPreset(p.id)}
                  className={`relative flex flex-col items-center gap-2 p-4 rounded-2xl border transition-all duration-200 ${
                    isActive ? 'border-sar bg-slate-800' : 'border-slate-800 bg-slate-900 hover:border-slate-700'
                  }`}>
                  {isActive && (
                    <div className="absolute inset-0 rounded-2xl opacity-10"
                      style={{ background: `radial-gradient(circle, ${p.accent}, transparent)` }} />
                  )}
                  <Icon size={22} style={{ color: isActive ? p.accent : '#475569' }} />
                  <span className={`text-xs font-bold ${isActive ? 'text-white' : 'text-slate-500'}`}>{p.label}</span>
                  <span className="text-xs text-slate-600 text-center leading-tight">{p.desc}</span>
                  {isActive && (
                    <div className="absolute top-2 right-2 w-2 h-2 rounded-full" style={{ backgroundColor: p.accent }} />
                  )}
                </motion.button>
              );
            })}
          </div>
        </motion.section>

        {/* Section 2: Toolbar */}
        <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="mb-8">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs text-slate-500 uppercase tracking-widest font-semibold">Your Bottom Toolbar</h2>
            <span className="text-xs text-slate-600">{selectedItems.length}/5 selected</span>
          </div>
          <div className="grid grid-cols-4 gap-2 mb-4">
            {TOOLBAR_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = selectedItems.includes(item.id);
              return (
                <motion.button key={item.id} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={() => toggleItem(item.id)}
                  className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border transition-all duration-200 ${
                    isActive ? 'border-sar bg-slate-800 text-sar' : 'border-slate-800 bg-slate-900 text-slate-500 hover:border-slate-700'
                  }`}>
                  <Icon size={18} />
                  <span className="text-xs font-medium">{item.label}</span>
                </motion.button>
              );
            })}
          </div>

          {/* Preview bar */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3">
            <p className="text-xs text-slate-600 mb-2 text-center">Preview</p>
            <div className="flex items-center justify-around">
              {selectedItems.map((id) => {
                const item = TOOLBAR_ITEMS.find((t) => t.id === id);
                if (!item) return null;
                const Icon = item.icon;
                return (
                  <div key={id} className="flex flex-col items-center gap-1">
                    <Icon size={20} style={{ color: themeColor }} />
                    <span className="text-xs text-slate-500">{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </motion.section>

        {/* Section 3: Theme Color */}
        <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="mb-8">
          <h2 className="text-xs text-slate-500 uppercase tracking-widest mb-3 font-semibold">Theme Color</h2>
          <div className="flex gap-3 flex-wrap">
            {THEME_COLORS.map((c) => (
              <motion.button key={c.id} whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}
                onClick={() => setThemeColor(c.value)}
                className="relative w-10 h-10 rounded-full border-2 transition-all duration-200"
                style={{
                  backgroundColor: c.value,
                  borderColor: themeColor === c.value ? '#ffffff' : 'transparent',
                  boxShadow: themeColor === c.value ? `0 0 0 3px ${c.value}40` : 'none',
                }}>
                {themeColor === c.value && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-2 h-2 bg-white rounded-full" />
                  </div>
                )}
              </motion.button>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-2">
            {THEME_COLORS.find((c) => c.value === themeColor)?.label}
          </p>
        </motion.section>

        {/* CTA */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            onClick={handleDone}
            className="w-full flex items-center justify-center gap-2 font-bold text-black text-lg py-4 rounded-2xl"
            style={{ backgroundColor: themeColor }}>
            Let's Go! <ChevronRight size={20} />
          </motion.button>
          <p className="text-slate-700 text-xs text-center mt-3">You can change this anytime in Settings</p>
        </motion.div>
      </div>
    </div>
  );
}
