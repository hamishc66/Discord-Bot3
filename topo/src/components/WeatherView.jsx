import { motion } from 'framer-motion';
import { Cloud, Sun, CloudRain, Snowflake, Wind, Droplets, Eye, Zap } from 'lucide-react';
import { mockWeather } from '../mockDatabase';

const weatherData = mockWeather[0];

const ICON_MAP = {
  sun: Sun,
  cloud: Cloud,
  'cloud-rain': CloudRain,
  snowflake: Snowflake,
  'cloud-sun': Cloud,
};

function WeatherIcon({ icon, size = 24, style }) {
  const Icon = ICON_MAP[icon] || Cloud;
  return <Icon size={size} style={style} />;
}

export default function WeatherView({ themeColor }) {
  return (
    <div className="pb-4">
      <div className="px-4 pt-4">
        {/* Main card */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="relative rounded-3xl overflow-hidden p-6 mb-4"
          style={{ background: `linear-gradient(135deg, ${themeColor}20, #0f172a)`, border: `1px solid ${themeColor}30` }}>
          
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-slate-400 text-sm mb-1">{weatherData.location}</p>
              <div className="flex items-end gap-2">
                <span className="text-7xl font-black text-white leading-none">{weatherData.tempC}°</span>
                <span className="text-slate-400 text-xl mb-2">C</span>
              </div>
              <p className="text-slate-300 mt-1">{weatherData.conditions}</p>
            </div>
            <div className="p-3 rounded-2xl" style={{ backgroundColor: `${themeColor}20` }}>
              <Cloud size={40} style={{ color: themeColor }} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Wind, label: 'Wind', value: `${weatherData.windKph} km/h` },
              { icon: Droplets, label: 'Humidity', value: `${weatherData.humidity}%` },
              { icon: Eye, label: 'Visibility', value: `${weatherData.visibility} km` },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className="bg-black/20 rounded-2xl p-3">
                  <Icon size={16} style={{ color: themeColor }} className="mb-1" />
                  <p className="text-white font-bold text-sm">{stat.value}</p>
                  <p className="text-slate-500 text-xs">{stat.label}</p>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* UV & alerts */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="topo-card p-4 mb-4 flex items-center gap-3">
          <div className="p-2 rounded-xl" style={{ backgroundColor: '#f59e0b20' }}>
            <Zap size={18} style={{ color: '#f59e0b' }} />
          </div>
          <div className="flex-1">
            <p className="text-white text-sm font-semibold">UV Index: {weatherData.uvIndex}</p>
            <p className="text-slate-500 text-xs">High — sun protection recommended above treeline</p>
          </div>
        </motion.div>

        {/* 5-day forecast */}
        <h3 className="text-xs text-slate-500 uppercase tracking-widest mb-3 font-semibold">5-Day Forecast</h3>
        <div className="grid grid-cols-5 gap-2">
          {weatherData.forecast.map((day, i) => (
            <motion.div key={day.day} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
              className="topo-card p-3 flex flex-col items-center gap-2">
              <p className="text-slate-500 text-xs font-semibold">{day.day}</p>
              <WeatherIcon icon={day.icon} size={20} style={{ color: themeColor }} />
              <p className="text-white text-sm font-bold">{day.tempHigh}°</p>
              <p className="text-slate-600 text-xs">{day.tempLow}°</p>
            </motion.div>
          ))}
        </div>

        {/* Trail warning */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
          className="mt-4 rounded-2xl p-4 border border-amber-500/30 bg-amber-500/5">
          <p className="text-amber-400 text-sm font-bold mb-1">⚠ Trail Advisory</p>
          <p className="text-slate-400 text-xs">Storm system approaching from the west. Strong gusty winds expected above 2000m from Wednesday afternoon. Avoid exposed ridgelines.</p>
        </motion.div>
      </div>
    </div>
  );
}
