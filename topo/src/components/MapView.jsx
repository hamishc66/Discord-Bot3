import { motion } from 'framer-motion';
import { MapPin, Users, Navigation, Compass } from 'lucide-react';

function TopoMapSVG({ themeColor }) {
  const contours = [
    "M50,300 C150,250 250,320 350,280 S500,250 600,300 S750,320 850,270",
    "M50,350 C180,290 280,360 380,320 S530,290 630,340 S780,360 880,310",
    "M50,250 C120,210 220,270 320,230 S470,210 570,260 S720,280 820,230",
    "M50,400 C200,340 300,400 400,360 S560,340 660,380 S810,400 910,360",
    "M50,200 C100,170 200,220 300,180 S450,170 550,210 S700,230 800,190",
    "M50,450 C220,390 320,450 420,410 S590,390 690,430 S840,450 940,410",
    "M50,150 C80,130 180,170 280,140 S430,130 530,160 S680,180 780,150",
    "M100,500 C240,440 340,490 440,460 S610,440 710,480",
  ];

  return (
    <svg viewBox="0 0 900 550" className="w-full h-full" preserveAspectRatio="xMidYMid slice">
      {/* Grid */}
      {Array.from({ length: 20 }).map((_, i) => (
        <line key={`v${i}`} x1={i * 50} y1={0} x2={i * 50} y2={600} stroke="#1e293b" strokeWidth="0.5" />
      ))}
      {Array.from({ length: 12 }).map((_, i) => (
        <line key={`h${i}`} x1={0} y1={i * 50} x2={1000} y2={i * 50} stroke="#1e293b" strokeWidth="0.5" />
      ))}
      {/* Contour lines */}
      {contours.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={themeColor} strokeWidth="1"
          opacity={0.15 + (i % 3) * 0.05} strokeLinecap="round" />
      ))}
      {/* Current location */}
      <circle cx="450" cy="275" r="8" fill={themeColor} opacity="0.9" />
      <circle cx="450" cy="275" r="20" fill={themeColor} opacity="0.15" />
      <circle cx="450" cy="275" r="35" fill={themeColor} opacity="0.07" />
    </svg>
  );
}

const nearbyTrails = [
  { name: 'Ridge Loop East', distance: '0.4 km', difficulty: 'Moderate', active: 12 },
  { name: 'Summit Approach', distance: '2.1 km', difficulty: 'Hard', active: 5 },
  { name: 'Valley Floor Trail', distance: '0.8 km', difficulty: 'Easy', active: 23 },
];

export default function MapView({ themeColor }) {
  return (
    <div className="h-full flex flex-col">
      {/* Map area */}
      <div className="relative flex-1 bg-slate-900 overflow-hidden min-h-0" style={{ minHeight: '300px' }}>
        <TopoMapSVG themeColor={themeColor} />

        {/* Overlay UI */}
        <div className="absolute top-3 left-3 glass rounded-xl px-3 py-2 flex items-center gap-2">
          <Navigation size={14} style={{ color: themeColor }} />
          <span className="text-xs text-white font-semibold">Summit Ridge</span>
        </div>
        <div className="absolute top-3 right-3 glass rounded-xl px-3 py-2">
          <Compass size={18} style={{ color: themeColor }} />
        </div>
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 glass rounded-xl px-4 py-2 flex items-center gap-2">
          <MapPin size={14} style={{ color: themeColor }} />
          <span className="text-xs text-white">37.4254° N, 122.0891° W</span>
        </div>
      </div>

      {/* Info cards */}
      <div className="flex-shrink-0 p-4 space-y-3 bg-slate-950">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Users size={14} style={{ color: themeColor }} /> Nearby Trails
        </h3>
        {nearbyTrails.map((trail, i) => (
          <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="topo-card p-3 flex items-center justify-between">
            <div>
              <p className="text-white text-sm font-semibold">{trail.name}</p>
              <p className="text-slate-500 text-xs">{trail.distance} away · {trail.difficulty}</p>
            </div>
            <div className="flex items-center gap-1 text-xs" style={{ color: themeColor }}>
              <Users size={12} />
              <span>{trail.active}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
