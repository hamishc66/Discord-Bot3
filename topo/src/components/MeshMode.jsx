import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Radio, Wifi, Signal } from 'lucide-react';
import { mockMeshNodes } from '../mockDatabase';

function RadarDisplay({ themeColor, nodes }) {
  return (
    <div className="relative w-64 h-64 mx-auto">
      {/* Concentric circles */}
      {[1, 0.75, 0.5, 0.25].map((scale, i) => (
        <div key={i} className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border"
          style={{
            width: `${scale * 100}%`, height: `${scale * 100}%`,
            borderColor: `${themeColor}30`,
          }} />
      ))}

      {/* Pulse rings */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full rounded-full pulse-ring"
        style={{ border: `1px solid ${themeColor}40` }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full rounded-full pulse-ring-2"
        style={{ border: `1px solid ${themeColor}30` }} />

      {/* Sweep line */}
      <div className="absolute top-1/2 left-1/2 w-1/2 h-0.5 radar-sweep origin-left"
        style={{
          background: `linear-gradient(to right, ${themeColor}, transparent)`,
          transformOrigin: '0 50%',
        }} />

      {/* Center dot */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full"
        style={{ backgroundColor: themeColor }} />

      {/* Node blips */}
      {nodes.map((node) => (
        <div key={node.id}
          className="absolute w-3 h-3 rounded-full blip"
          style={{
            backgroundColor: node.avatarColor,
            left: `${node.x}%`,
            top: `${node.y}%`,
            transform: 'translate(-50%, -50%)',
            boxShadow: `0 0 6px ${node.avatarColor}`,
          }}
        />
      ))}
    </div>
  );
}

export default function MeshMode({ user, themeColor }) {
  const [messages, setMessages] = useState([
    { id: 1, from: 'sierra_walker', text: 'Anyone on ridge approach? Conditions?', time: '14:22', color: '#3b82f6' },
    { id: 2, from: 'You', text: 'Clear up to 2400m. Wind picking up above.', time: '14:23', color: themeColor, self: true },
    { id: 3, from: 'ranger_k', text: 'SAR team on standby at base. Stay safe.', time: '14:25', color: '#ef4444' },
  ]);
  const [input, setInput] = useState('');
  const [nodeCount] = useState(mockMeshNodes.length);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, {
      id: Date.now(),
      from: 'You',
      text: input,
      time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      color: themeColor,
      self: true,
    }]);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div className="h-full flex flex-col" style={{ background: 'radial-gradient(ellipse at center, #0d1b2a 0%, #020617 70%)' }}>
      {/* Header */}
      <div className="px-4 pt-4 pb-2 flex-shrink-0">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Radio size={20} style={{ color: themeColor }} className="animate-pulse" />
            <span className="font-black text-white text-lg">MESH MODE</span>
          </div>
          <div className="flex items-center gap-1.5 glass px-3 py-1.5 rounded-full">
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: themeColor }} />
            <span className="text-xs font-semibold" style={{ color: themeColor }}>ACTIVE</span>
          </div>
        </div>
        <p className="text-slate-500 text-xs">P2P Burst Network · Encrypted · Offline-ready</p>
      </div>

      {/* Radar */}
      <div className="flex-shrink-0 py-4">
        <RadarDisplay themeColor={themeColor} nodes={mockMeshNodes} />
        <div className="text-center mt-3">
          <span className="text-2xl font-black" style={{ color: themeColor }}>{nodeCount}</span>
          <span className="text-slate-500 text-sm ml-2">P2P Nodes Found</span>
        </div>
      </div>

      {/* Node list */}
      <div className="flex-shrink-0 px-4 mb-3">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {mockMeshNodes.map((node) => (
            <div key={node.id} className="flex-shrink-0 glass rounded-xl px-3 py-2 flex items-center gap-2">
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-black text-xs font-bold"
                style={{ backgroundColor: node.avatarColor }}>
                {node.username[0].toUpperCase()}
              </div>
              <div>
                <p className="text-xs text-white font-semibold">{node.username}</p>
                <div className="flex items-center gap-1">
                  <Signal size={10} style={{ color: node.signalStrength > 70 ? '#22c55e' : node.signalStrength > 50 ? '#f59e0b' : '#ef4444' }} />
                  <span className="text-xs text-slate-500">{node.signalStrength}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat */}
      <div className="flex-1 flex flex-col min-h-0 px-4">
        <p className="text-xs text-slate-600 uppercase tracking-widest mb-2 flex items-center gap-1">
          <Wifi size={10} /> Local Burst Messages
        </p>
        <div className="flex-1 overflow-y-auto space-y-2 mb-3 min-h-0" style={{ maxHeight: '180px' }}>
          {messages.map((msg) => (
            <motion.div key={msg.id} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.self ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-xs rounded-2xl px-3 py-2 ${msg.self ? 'rounded-tr-sm' : 'rounded-tl-sm bg-slate-800'}`}
                style={msg.self ? { backgroundColor: `${themeColor}20`, border: `1px solid ${themeColor}40` } : {}}>
                {!msg.self && (
                  <p className="text-xs font-bold mb-0.5" style={{ color: msg.color }}>@{msg.from}</p>
                )}
                <p className="text-sm text-white">{msg.text}</p>
                <p className="text-xs text-slate-600 mt-1 text-right">{msg.time}</p>
              </div>
            </motion.div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 mb-2">
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
            placeholder="Burst message..."
            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-white placeholder-slate-600 focus:outline-none text-sm"
            style={{ borderColor: input ? `${themeColor}60` : '' }} />
          <motion.button whileTap={{ scale: 0.9 }} onClick={sendMessage}
            className="w-10 h-10 rounded-xl flex items-center justify-center text-black flex-shrink-0"
            style={{ backgroundColor: themeColor }}>
            <Send size={16} />
          </motion.button>
        </div>
      </div>
    </div>
  );
}
