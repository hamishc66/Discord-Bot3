import { motion, AnimatePresence } from 'framer-motion';
import { X, Home, User, Settings, Info, LogOut, Mountain } from 'lucide-react';

const menuItems = [
  { icon: Home, label: 'Home', action: 'home' },
  { icon: User, label: 'Profile', action: 'profile' },
  { icon: Settings, label: 'Settings', action: 'settings' },
  { icon: Info, label: 'About TOPO', action: 'about' },
];

export default function HamburgerMenu({ isOpen, onClose, user, onLogout, themeColor }) {
  const accent = themeColor || '#ff9100';

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" />
          <motion.div
            initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed left-0 top-0 h-full w-72 bg-slate-900 border-r border-slate-800 z-50 flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Mountain size={20} style={{ color: accent }} />
                <span className="font-black text-xl tracking-tight" style={{ color: accent }}>TOPO</span>
              </div>
              <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors p-1">
                <X size={20} />
              </button>
            </div>

            {/* User section */}
            <div className="p-5 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full flex items-center justify-center text-black font-bold text-lg"
                  style={{ backgroundColor: accent }}>
                  {(user?.username || 'U')[0].toUpperCase()}
                </div>
                <div>
                  <p className="font-bold text-white">{user?.username || 'Explorer'}</p>
                  <p className="text-xs text-slate-500">{user?.email || 'trail@topo.io'}</p>
                </div>
              </div>
            </div>

            {/* Menu items */}
            <nav className="flex-1 p-4 space-y-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <motion.button key={item.action} whileHover={{ x: 4 }}
                    onClick={onClose}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-all duration-200">
                    <Icon size={18} />
                    <span className="font-medium">{item.label}</span>
                  </motion.button>
                );
              })}
            </nav>

            {/* Logout */}
            <div className="p-4 border-t border-slate-800">
              <motion.button whileHover={{ x: 4 }} onClick={onLogout}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-400 hover:text-red-300 hover:bg-red-950/30 transition-all duration-200">
                <LogOut size={18} />
                <span className="font-medium">Log Out</span>
              </motion.button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
