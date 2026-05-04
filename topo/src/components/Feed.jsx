import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Heart, MessageCircle, Share2, Plus, X, Send, Cloud, Thermometer, Wind } from 'lucide-react';
import { mockPosts } from '../mockDatabase';

function PostCard({ post, onLike, themeColor }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className="topo-card p-4 mb-3">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center font-bold text-sm text-black"
          style={{ backgroundColor: post.avatarColor }}>
          {post.username[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white text-sm">@{post.username}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full text-black font-medium ${
              post.type === 'trail' ? 'bg-green-500/80' : post.type === 'gear' ? 'bg-blue-500/80' : 'bg-slate-700 text-slate-300'
            }`}>
              {post.type}
            </span>
          </div>
          <p className="text-xs text-slate-500">{post.timestamp}</p>
        </div>
      </div>
      <p className="text-slate-200 text-sm leading-relaxed mb-3">{post.content}</p>
      {post.imageUrl && (
        <div className="h-36 bg-slate-800 rounded-xl mb-3 flex items-center justify-center">
          <span className="text-slate-600 text-xs">[ Image ]</span>
        </div>
      )}
      <div className="flex items-center gap-4 pt-2 border-t border-slate-800/50">
        <button onClick={() => onLike(post.id)}
          className="flex items-center gap-1.5 transition-colors"
          style={{ color: post.liked ? themeColor : '#475569' }}>
          <Heart size={16} fill={post.liked ? themeColor : 'none'} stroke={post.liked ? themeColor : '#475569'} />
          <span className="text-xs">{post.likes}</span>
        </button>
        <button className="flex items-center gap-1.5 text-slate-500 hover:text-slate-300 transition-colors">
          <MessageCircle size={16} />
          <span className="text-xs">{post.comments}</span>
        </button>
        <button className="flex items-center gap-1.5 text-slate-500 hover:text-slate-300 transition-colors ml-auto">
          <Share2 size={16} />
        </button>
      </div>
    </motion.div>
  );
}

function WeatherWidget({ themeColor }) {
  return (
    <div className="topo-card p-3 mb-4 flex items-center gap-4">
      <div className="flex items-center gap-2">
        <Cloud size={20} style={{ color: themeColor }} />
        <span className="text-white font-bold text-lg">12°C</span>
      </div>
      <div className="flex items-center gap-1 text-slate-500 text-xs">
        <Wind size={14} />
        <span>28 km/h</span>
      </div>
      <div className="text-slate-500 text-xs">Summit Ridge</div>
      <div className="ml-auto text-xs" style={{ color: themeColor }}>Partly Cloudy</div>
    </div>
  );
}

function NewPostModal({ onClose, onPost, themeColor }) {
  const [text, setText] = useState('');
  const handleSubmit = () => {
    if (!text.trim()) return;
    onPost(text);
    onClose();
  };
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-end">
      <motion.div initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="w-full bg-slate-900 border-t border-slate-800 rounded-t-3xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-white">New Post</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={20} /></button>
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)}
          placeholder="What's happening on the trail?"
          rows={4}
          className="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-white placeholder-slate-600 resize-none focus:outline-none focus:border-sar text-sm" />
        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
          onClick={handleSubmit}
          className="w-full mt-3 py-3 rounded-xl flex items-center justify-center gap-2 font-bold text-black"
          style={{ backgroundColor: themeColor }}>
          <Send size={16} /> Post
        </motion.button>
      </motion.div>
    </motion.div>
  );
}

export default function Feed({ user, themeColor, showTabs }) {
  const [posts, setPosts] = useState(mockPosts);
  const [showModal, setShowModal] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('foryou');

  const handleLike = (id) => {
    setPosts((prev) => prev.map((p) =>
      p.id === id ? { ...p, liked: !p.liked, likes: p.liked ? p.likes - 1 : p.likes + 1 } : p
    ));
  };

  const handleNewPost = (text) => {
    const newPost = {
      id: Date.now(),
      username: user?.username || 'you',
      avatarColor: '#ff9100',
      content: text,
      imageUrl: null,
      likes: 0,
      comments: 0,
      timestamp: 'just now',
      type: 'general',
      liked: false,
    };
    setPosts([newPost, ...posts]);
  };

  const displayPosts = activeSubTab === 'trending'
    ? [...posts].sort((a, b) => b.likes - a.likes).slice(0, 10)
    : posts;

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="px-4 pt-4">
        <WeatherWidget themeColor={themeColor} />
        {showTabs && (
          <div className="flex gap-2 mb-4">
            {['foryou', 'trending'].map((tab) => (
              <button key={tab} onClick={() => setActiveSubTab(tab)}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
                  activeSubTab === tab ? 'text-black' : 'bg-slate-900 border border-slate-800 text-slate-400'
                }`}
                style={activeSubTab === tab ? { backgroundColor: themeColor } : {}}>
                {tab === 'foryou' ? 'For You' : '🔥 Trending'}
              </button>
            ))}
          </div>
        )}
        {!showTabs && (
          <h2 className="text-lg font-bold text-white mb-4">Your Feed</h2>
        )}
      </div>
      <div className="px-4">
        {displayPosts.map((post, i) => (
          <motion.div key={post.id} initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}>
            <PostCard post={post} onLike={handleLike} themeColor={themeColor} />
          </motion.div>
        ))}
      </div>

      {/* FAB */}
      <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.95 }}
        onClick={() => setShowModal(true)}
        className="fixed bottom-24 right-5 w-14 h-14 rounded-full flex items-center justify-center shadow-2xl z-30 text-black"
        style={{ backgroundColor: themeColor, boxShadow: `0 8px 30px ${themeColor}40` }}>
        <Plus size={24} strokeWidth={3} />
      </motion.button>

      <AnimatePresence>
        {showModal && (
          <NewPostModal onClose={() => setShowModal(false)} onPost={handleNewPost} themeColor={themeColor} />
        )}
      </AnimatePresence>
    </div>
  );
}
