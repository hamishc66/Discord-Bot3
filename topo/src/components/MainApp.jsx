import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mountain, Bell, Menu, House, LayoutDashboard, Map, Radio, Package, Cloud, Users, User } from 'lucide-react';
import HamburgerMenu from './HamburgerMenu';
import Feed from './Feed';
import MapView from './MapView';
import MeshMode from './MeshMode';
import GearLocker from './GearLocker';
import WeatherView from './WeatherView';
import CrewView from './CrewView';
import Profile from './Profile';

const ICON_MAP = { home: House, feed: LayoutDashboard, map: Map, mesh: Radio, gear: Package, weather: Cloud, crew: Users, profile: User };
const LABEL_MAP = { home: 'Home', feed: 'Feed', map: 'Map', mesh: 'Mesh', gear: 'Gear', weather: 'Weather', crew: 'Crew', profile: 'Profile' };
const DEFAULT_TOOLBAR = ['home', 'feed', 'map', 'mesh', 'profile'];

export default function MainApp({ user, config, onLogout }) {
  const toolbar = config?.toolbar || DEFAULT_TOOLBAR;
  const themeColor = config?.themeColor || '#ff9100';
  const [activeTab, setActiveTab] = useState(toolbar[0] || 'home');
  const [menuOpen, setMenuOpen] = useState(false);
  const [prevTab, setPrevTab] = useState(null);

  const handleTabChange = (tab) => {
    setPrevTab(activeTab);
    setActiveTab(tab);
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'home': return <Feed user={user} themeColor={themeColor} />;
      case 'feed': return <Feed user={user} themeColor={themeColor} showTabs />;
      case 'map': return <MapView themeColor={themeColor} />;
      case 'mesh': return <MeshMode user={user} themeColor={themeColor} />;
      case 'gear': return <GearLocker themeColor={themeColor} />;
      case 'weather': return <WeatherView themeColor={themeColor} />;
      case 'crew': return <CrewView themeColor={themeColor} />;
      case 'profile': return <Profile user={user} themeColor={themeColor} />;
      default: return <Feed user={user} themeColor={themeColor} />;
    }
  };

  const isMesh = activeTab === 'mesh';

  return (
    <div className={`w-full h-screen flex flex-col overflow-hidden transition-colors duration-500 ${isMesh ? 'bg-slate-950' : 'bg-slate-950'}`}>
      {/* Top bar */}
      <div className={`flex items-center justify-between px-4 py-3 border-b border-slate-800/50 glass flex-shrink-0 z-20`}>
        <button onClick={() => setMenuOpen(true)} className="text-slate-400 hover:text-white transition-colors p-1">
          <Menu size={22} />
        </button>
        <div className="flex items-center gap-1.5">
          <Mountain size={18} style={{ color: themeColor }} />
          <span className="font-black text-lg tracking-tight" style={{ color: themeColor }}>TOPO</span>
        </div>
        <div className="flex items-center gap-2">
          <button className="relative text-slate-400 hover:text-white transition-colors p-1">
            <Bell size={20} />
            <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-sar rounded-full" style={{ backgroundColor: themeColor }} />
          </button>
          <div className="w-8 h-8 rounded-full flex items-center justify-center text-black font-bold text-sm"
            style={{ backgroundColor: themeColor }}>
            {(user?.username || 'U')[0].toUpperCase()}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className="absolute inset-0 overflow-y-auto"
          >
            {renderContent()}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Bottom toolbar */}
      <div className="flex-shrink-0 glass border-t border-slate-800/50 z-20">
        <div className="flex items-center justify-around px-2 py-2">
          {toolbar.map((id) => {
            const Icon = ICON_MAP[id] || House;
            const isActive = activeTab === id;
            return (
              <motion.button key={id} whileTap={{ scale: 0.9 }}
                onClick={() => handleTabChange(id)}
                className="flex flex-col items-center gap-1 px-3 py-2 rounded-xl transition-all duration-200 min-w-0">
                <div className={`p-1.5 rounded-xl transition-all duration-200 ${isActive ? 'bg-slate-800' : ''}`}>
                  <Icon size={20} style={{ color: isActive ? themeColor : '#475569' }} strokeWidth={isActive ? 2.5 : 2} />
                </div>
                <span className="text-xs transition-colors duration-200 truncate"
                  style={{ color: isActive ? themeColor : '#475569', fontSize: '10px' }}>
                  {LABEL_MAP[id]}
                </span>
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Hamburger drawer */}
      <HamburgerMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)}
        user={user} onLogout={onLogout} themeColor={themeColor} />
    </div>
  );
}
