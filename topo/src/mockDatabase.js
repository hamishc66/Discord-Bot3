// TOPO Mock Database

export const mockPosts = [
  { id: 1, username: 'alpinetrack', avatarColor: '#ff9100', content: 'Just crushed the Ridge Loop in 2h45m — new PR! The views from the summit were absolutely insane today. 🏔️', imageUrl: null, likes: 47, comments: 12, timestamp: '2m ago', type: 'trail', liked: false },
  { id: 2, username: 'sierra_walker', avatarColor: '#3b82f6', content: 'Heads up — switchbacks on the North Face trail have some fresh rockfall. Stay right past the 3km marker. Safety first 🪨', imageUrl: null, likes: 83, comments: 29, timestamp: '15m ago', type: 'general', liked: false },
  { id: 3, username: 'gear_nerd_07', avatarColor: '#22c55e', content: 'Finally replaced my aging shelter — Black Diamond Hilight 3P. Packed a full day yesterday through wind & rain. Zero issues. Highly recommend for alpine conditions.', imageUrl: null, likes: 31, comments: 8, timestamp: '42m ago', type: 'gear', liked: false },
  { id: 4, username: 'dusty_miles', avatarColor: '#a855f7', content: '50km trail run done. Legs are toast but mind is fresh. Nothing beats dawn light on the Escarpment. Mesh worked great connecting with @sierra_walker mid-route.', imageUrl: null, likes: 112, comments: 45, timestamp: '1h ago', type: 'trail', liked: false },
  { id: 5, username: 'ranger_k', avatarColor: '#ef4444', content: 'Search and rescue drill complete. Team TOPO mesh coordination was seamless — 8 nodes across 12km², zero comms blackout. This tech is a game changer for SAR.', imageUrl: null, likes: 209, comments: 67, timestamp: '2h ago', type: 'general', liked: false },
  { id: 6, username: 'nomad_pixels', avatarColor: '#ff9100', content: 'Waterfall Canyon sunset. Spent 3 days off-grid on the Southern Traverse. Mesh kept me connected with base camp the whole way. TOPO nodes are becoming essential kit.', imageUrl: null, likes: 158, comments: 34, timestamp: '3h ago', type: 'trail', liked: false },
  { id: 7, username: 'cliff_hangers', avatarColor: '#3b82f6', content: 'New PB on the Granite Wall — 5.12c clean on the crux! Finally stuck the move I\'ve been projecting for 6 weeks. Big shoutout to the crew for the beta. 💪', imageUrl: null, likes: 76, comments: 23, timestamp: '4h ago', type: 'trail', liked: false },
  { id: 8, username: 'trail_medic', avatarColor: '#22c55e', content: 'Reminder: check your first aid kit before any remote trip. I\'ve updated the TOPO Gear checklist — see the Gear Locker for the full list. Stay safe out there.', imageUrl: null, likes: 94, comments: 17, timestamp: '5h ago', type: 'gear', liked: false },
  { id: 9, username: 'mesa_runner', avatarColor: '#f97316', content: 'Red Rock Canyon 30km done. 38°C heat but the early start made it manageable. Weather widget on TOPO saved my pack planning this morning ☀️', imageUrl: null, likes: 55, comments: 11, timestamp: '6h ago', type: 'trail', liked: false },
  { id: 10, username: 'peak_chaser', avatarColor: '#06b6d4', content: '14th summit this season. One more and I complete the full circuit. Who else is trying the winter version? Looking to connect with crew for January conditions. ❄️', imageUrl: null, likes: 143, comments: 52, timestamp: '7h ago', type: 'trail', liked: false },
  { id: 11, username: 'forest_ghost', avatarColor: '#84cc16', content: 'Night navigation practice in Pine Barrens. No phone, no GPS — just compass, topo map, and TOPO Mesh for emergency evac. Skills first, tech backup. Old school.', imageUrl: null, likes: 88, comments: 28, timestamp: '8h ago', type: 'general', liked: false },
  { id: 12, username: 'base_camp_radio', avatarColor: '#ec4899', content: 'TOPO Mesh firmware v2.3.1 dropped — improved range by ~15% and battery life gains across the board. Update via the Gear menu. Huge W for long expeditions.', imageUrl: null, likes: 317, comments: 89, timestamp: '9h ago', type: 'gear', liked: false },
  { id: 13, username: 'ironwood_hiker', avatarColor: '#8b5cf6', content: 'Quiet day on the Ironwood Loop. Just me, the pines, and 18km of silence. Needed this reset. Found a hidden spring at km 11 — adding to the community map now.', imageUrl: null, likes: 67, comments: 19, timestamp: '10h ago', type: 'trail', liked: false },
  { id: 14, username: 'alpine_doc', avatarColor: '#ef4444', content: 'High-altitude pulmonary edema is real. Ascending too fast above 3500m is dangerous. The TOPO health monitor caught my elevated resting HR on day 3. Turned back. Live to hike another day.', imageUrl: null, likes: 402, comments: 134, timestamp: '11h ago', type: 'general', liked: false },
  { id: 15, username: 'bivy_queen', avatarColor: '#ff9100', content: 'Cowboy camping under the Milky Way on the desert plateau. Minus 4°C, zero dew, perfect stars. Sometimes the best shelter is no shelter. 🌌', imageUrl: null, likes: 229, comments: 41, timestamp: '12h ago', type: 'trail', liked: false },
  { id: 16, username: 'gear_tester_x', avatarColor: '#3b82f6', content: 'Week-long field test on the Osprey Atmos 65L. The mesh back panel is genuinely breathable. Loaded to 18kg, no hot spots. Final verdict: 9/10 for technical mountain use.', imageUrl: null, likes: 71, comments: 22, timestamp: '14h ago', type: 'gear', liked: false },
  { id: 17, username: 'canyon_crew', avatarColor: '#22c55e', content: 'Our crew of 6 completed the 5-day canyon traverse! 120km, 4200m elevation gain. TOPO Mesh kept the whole group connected across every gorge. Proud of every member. 🎉', imageUrl: null, likes: 445, comments: 112, timestamp: '16h ago', type: 'trail', liked: false },
  { id: 18, username: 'weather_eye', avatarColor: '#0ea5e9', content: 'Storm cells forming over the western ranges — expect strong gusty winds above 2000m from tomorrow afternoon. Avoid exposed ridgelines. Updated forecast in TOPO Weather.', imageUrl: null, likes: 298, comments: 63, timestamp: '18h ago', type: 'general', liked: false },
  { id: 19, username: 'summit_grind', avatarColor: '#a855f7', content: 'Training week: 85km, 5200m vert. Feeling strong for next month\'s 100-miler. Diet, sleep, and elevation exposure are the only secrets. Consistency > everything.', imageUrl: null, likes: 187, comments: 47, timestamp: '20h ago', type: 'trail', liked: false },
  { id: 20, username: 'mountain_medic', avatarColor: '#f59e0b', content: 'First aid refresher complete. All TOPO crew leaders should carry a wilderness first aid cert. Link to certified courses in my profile. Know what to do when you\'re hours from evac.', imageUrl: null, likes: 156, comments: 38, timestamp: '22h ago', type: 'general', liked: false },
  { id: 21, username: 'night_owl_trails', avatarColor: '#64748b', content: 'Headlamp comparison: Black Diamond Spot 400 vs Petzl Actik Core. Both solid but BD wins for throw distance. For technical night moves, the beam control is unmatched.', imageUrl: null, likes: 43, comments: 15, timestamp: '1d ago', type: 'gear', liked: false },
  { id: 22, username: 'highline_hank', avatarColor: '#ef4444', content: 'Slackline session at 2800m — 35m across the ridge gap. Wind was sketchy but the anchors held. Always triple-check your rigging at altitude. No margin for error.', imageUrl: null, likes: 321, comments: 78, timestamp: '1d ago', type: 'trail', liked: false },
  { id: 23, username: 'packraft_pro', avatarColor: '#06b6d4', content: 'Packrafted the full river section of the Wilderness Arc — 22km of Class II-III. TOPO Mesh pinged my position every 30 mins to shore crew. Seamless water-to-land comms. 🛶', imageUrl: null, likes: 267, comments: 59, timestamp: '2d ago', type: 'trail', liked: false },
  { id: 24, username: 'zero_dark_thirty', avatarColor: '#1e293b', content: 'Alpine start at 01:30. Summit by 06:15. Back at trailhead by noon. Clean. Efficient. The mountain doesn\'t care about your schedule — respect it and it rewards you. 🌄', imageUrl: null, likes: 512, comments: 143, timestamp: '2d ago', type: 'trail', liked: false },
  { id: 25, username: 'topo_founder', avatarColor: '#ff9100', content: 'TOPO hit 100,000 users this week. Started as a mesh radio experiment in a tent, now powering SAR ops and expedition crews globally. Thank you to every trailblazer who believed early. The mission continues. 🏔️📡', imageUrl: null, likes: 2847, comments: 634, timestamp: '3d ago', type: 'general', liked: false },
];

export const mockGear = [
  { id: 1, name: 'Black Diamond Hilight 3P', type: 'Shelter', weightKg: 1.1, brand: 'Black Diamond', safetyStatus: 'good', lastChecked: '2025-04-28' },
  { id: 2, name: 'Osprey Atmos AG 65', type: 'Pack', weightKg: 2.1, brand: 'Osprey', safetyStatus: 'good', lastChecked: '2025-04-15' },
  { id: 3, name: 'MSR Hubba Hubba NX2', type: 'Shelter', weightKg: 1.7, brand: 'MSR', safetyStatus: 'check', lastChecked: '2025-03-01' },
  { id: 4, name: 'Jetboil Flash Cooking System', type: 'Cooking', weightKg: 0.4, brand: 'Jetboil', safetyStatus: 'good', lastChecked: '2025-04-20' },
  { id: 5, name: 'Black Diamond Spot 400 Headlamp', type: 'Lighting', weightKg: 0.1, brand: 'Black Diamond', safetyStatus: 'good', lastChecked: '2025-04-25' },
  { id: 6, name: 'Petzl Corax 35 Harness', type: 'Climbing', weightKg: 0.5, brand: 'Petzl', safetyStatus: 'check', lastChecked: '2025-02-10' },
  { id: 7, name: 'TOPO Mesh Node MK2', type: 'Electronics', weightKg: 0.2, brand: 'TOPO', safetyStatus: 'good', lastChecked: '2025-04-30' },
  { id: 8, name: 'Lifestraw Peak Series Filter', type: 'Water', weightKg: 0.06, brand: 'Lifestraw', safetyStatus: 'good', lastChecked: '2025-04-18' },
  { id: 9, name: 'Black Diamond Camalots Set x5', type: 'Climbing', weightKg: 0.8, brand: 'Black Diamond', safetyStatus: 'flagged', lastChecked: '2025-01-05' },
  { id: 10, name: 'Wilderness First Aid Kit', type: 'Medical', weightKg: 0.45, brand: 'Adventure Medical', safetyStatus: 'check', lastChecked: '2025-03-15' },
  { id: 11, name: 'Garmin inReach Mini 2', type: 'Navigation', weightKg: 0.1, brand: 'Garmin', safetyStatus: 'good', lastChecked: '2025-04-29' },
  { id: 12, name: 'Mammut Crag Sender 9.5mm 60m', type: 'Climbing', weightKg: 3.5, brand: 'Mammut', safetyStatus: 'flagged', lastChecked: '2024-12-01' },
];

export const mockWeather = [
  {
    location: 'Summit Ridge',
    tempC: 12,
    conditions: 'Partly Cloudy',
    windKph: 28,
    humidity: 54,
    uvIndex: 6,
    visibility: 18,
    forecast: [
      { day: 'Mon', tempHigh: 14, tempLow: 4, conditions: 'Sunny', icon: 'sun' },
      { day: 'Tue', tempHigh: 11, tempLow: 2, conditions: 'Cloudy', icon: 'cloud' },
      { day: 'Wed', tempHigh: 8, tempLow: -1, conditions: 'Rain', icon: 'cloud-rain' },
      { day: 'Thu', tempHigh: 6, tempLow: -3, conditions: 'Snow', icon: 'snowflake' },
      { day: 'Fri', tempHigh: 9, tempLow: 0, conditions: 'Partly Cloudy', icon: 'cloud-sun' },
    ],
  },
  {
    location: 'Valley Base',
    tempC: 22,
    conditions: 'Clear',
    windKph: 12,
    humidity: 38,
    uvIndex: 8,
    visibility: 25,
    forecast: [
      { day: 'Mon', tempHigh: 24, tempLow: 14, conditions: 'Sunny', icon: 'sun' },
      { day: 'Tue', tempHigh: 23, tempLow: 13, conditions: 'Sunny', icon: 'sun' },
      { day: 'Wed', tempHigh: 19, tempLow: 11, conditions: 'Cloudy', icon: 'cloud' },
      { day: 'Thu', tempHigh: 17, tempLow: 9, conditions: 'Rain', icon: 'cloud-rain' },
      { day: 'Fri', tempHigh: 21, tempLow: 12, conditions: 'Partly Cloudy', icon: 'cloud-sun' },
    ],
  },
];

export const mockCrew = [
  { id: 1, username: 'sierra_walker', avatarColor: '#3b82f6', distanceKm: 0.4, lastActive: '3m ago', trail: 'Ridge Loop East', status: 'active' },
  { id: 2, username: 'dusty_miles', avatarColor: '#a855f7', distanceKm: 1.2, lastActive: '12m ago', trail: 'Summit Approach', status: 'active' },
  { id: 3, username: 'ranger_k', avatarColor: '#ef4444', distanceKm: 2.7, lastActive: '28m ago', trail: 'North Face', status: 'idle' },
  { id: 4, username: 'cliff_hangers', avatarColor: '#22c55e', distanceKm: 0.8, lastActive: '5m ago', trail: 'Granite Wall Base', status: 'active' },
  { id: 5, username: 'bivy_queen', avatarColor: '#ff9100', distanceKm: 4.1, lastActive: '1h ago', trail: 'Desert Plateau', status: 'idle' },
  { id: 6, username: 'mesa_runner', avatarColor: '#f97316', distanceKm: 3.3, lastActive: '47m ago', trail: 'Red Rock Canyon', status: 'idle' },
  { id: 7, username: 'forest_ghost', avatarColor: '#84cc16', distanceKm: 6.8, lastActive: '2h ago', trail: 'Pine Barrens Loop', status: 'offline' },
  { id: 8, username: 'packraft_pro', avatarColor: '#06b6d4', distanceKm: 9.2, lastActive: '3h ago', trail: 'River Gorge', status: 'offline' },
];

export const mockMeshNodes = [
  { id: 1, username: 'sierra_walker', avatarColor: '#3b82f6', signalStrength: 92, x: 48, y: 35 },
  { id: 2, username: 'dusty_miles', avatarColor: '#a855f7', signalStrength: 78, x: 62, y: 58 },
  { id: 3, username: 'cliff_hangers', avatarColor: '#22c55e', signalStrength: 85, x: 35, y: 62 },
  { id: 4, username: 'ranger_k', avatarColor: '#ef4444', signalStrength: 61, x: 72, y: 28 },
  { id: 5, username: 'nomad_pixels', avatarColor: '#ff9100', signalStrength: 44, x: 25, y: 42 },
];
