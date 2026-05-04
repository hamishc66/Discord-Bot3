import { useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Welcome from './components/Welcome';
import Customise from './components/Customise';
import MainApp from './components/MainApp';

const SCREEN = { WELCOME: 'welcome', CUSTOMISE: 'customise', MAIN: 'main' };

export default function App() {
  const [screen, setScreen] = useState(SCREEN.WELCOME);
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const [direction, setDirection] = useState(1);

  useEffect(() => {
    const savedUser = localStorage.getItem('topo_user');
    const savedConfig = localStorage.getItem('topo_config');
    if (savedUser && savedConfig) {
      setUser(JSON.parse(savedUser));
      setConfig(JSON.parse(savedConfig));
      setScreen(SCREEN.MAIN);
    } else if (savedUser) {
      setUser(JSON.parse(savedUser));
      setScreen(SCREEN.CUSTOMISE);
    }
  }, []);

  const handleSignUp = (userData) => {
    localStorage.setItem('topo_user', JSON.stringify(userData));
    setUser(userData);
    setDirection(1);
    setScreen(SCREEN.CUSTOMISE);
  };

  const handleLogin = (userData) => {
    setUser(userData);
    setDirection(1);
    setScreen(SCREEN.MAIN);
  };

  const handleCustomiseDone = (configData) => {
    localStorage.setItem('topo_config', JSON.stringify(configData));
    setConfig(configData);
    setDirection(1);
    setScreen(SCREEN.MAIN);
  };

  const handleLogout = () => {
    localStorage.removeItem('topo_user');
    localStorage.removeItem('topo_config');
    setUser(null);
    setConfig(null);
    setDirection(-1);
    setScreen(SCREEN.WELCOME);
  };

  const pageVariants = {
    initial: (dir) => ({ opacity: 0, x: dir > 0 ? 60 : -60 }),
    animate: { opacity: 1, x: 0 },
    exit: (dir) => ({ opacity: 0, x: dir > 0 ? -60 : 60 }),
  };

  return (
    <div className="relative w-full min-h-screen bg-slate-950 overflow-hidden">
      <AnimatePresence mode="wait" custom={direction}>
        {screen === SCREEN.WELCOME && (
          <motion.div key="welcome" custom={direction} variants={pageVariants}
            initial="initial" animate="animate" exit="exit"
            transition={{ duration: 0.4, ease: 'easeInOut' }} className="absolute inset-0">
            <Welcome onSignUp={handleSignUp} onLogin={handleLogin} />
          </motion.div>
        )}
        {screen === SCREEN.CUSTOMISE && (
          <motion.div key="customise" custom={direction} variants={pageVariants}
            initial="initial" animate="animate" exit="exit"
            transition={{ duration: 0.4, ease: 'easeInOut' }} className="absolute inset-0">
            <Customise user={user} onDone={handleCustomiseDone} />
          </motion.div>
        )}
        {screen === SCREEN.MAIN && (
          <motion.div key="main" custom={direction} variants={pageVariants}
            initial="initial" animate="animate" exit="exit"
            transition={{ duration: 0.4, ease: 'easeInOut' }} className="absolute inset-0">
            <MainApp user={user} config={config} onLogout={handleLogout} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
