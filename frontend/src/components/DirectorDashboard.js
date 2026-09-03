import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import JSZip from 'jszip';
import DashboardLayout from './DashboardLayout';
import { DonutChart } from './DashCharts';
import './Dashboard.css';

const API_URL = 'http://localhost:8000';

const DocsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
);

function DirectorDashboard({ user, onClose, onLogout }) {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [allTranscriptions, setAllTranscriptions] = useState([]);
  const [activeTab, setActiveTab] = useState('transcriptions');
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [viewingTranscription, setViewingTranscription] = useState(null);
  const [downloadingCategory, setDownloadingCategory] = useState(false);
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const audioRef = useRef(null);
  
  // Filter states
  const [filterType, setFilterType] = useState('all');
  const [filterUser, setFilterUser] = useState('all');
  const [filterDate, setFilterDate] = useState('all');
  const [filterLanguage, setFilterLanguage] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'secretary',
    department: ''
  });

  // Quick stats for dashboard header
  const totalUsers = users.length;
  const totalTranscriptions = allTranscriptions.length;
  const totalEnglish = allTranscriptions.filter(r => r.language_detected === 'en').length;
  const totalKinyarwanda = allTranscriptions.filter(r => r.language_detected === 'rw').length;

  const api = axios.create({
    baseURL: API_URL,
  });

  api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  const fetchAllData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchStats(),
        fetchUsers(),
        fetchActivity(),
        fetchAllTranscriptions()
      ]);
    } catch (err) {
      console.error('Error fetching data:', err);
      showMessage('error', 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  // Helper: map user id to display name
  const getUserName = (userId) => {
    const u = users.find(x => x.id === userId);
    return u ? (u.full_name || u.username) : `User ${userId}`;
  };

  const getTranscriptionType = (record) => {
    if (!record || !record.filename) return { icon: '🎵', label: 'Audio' };
    const name = record.filename.toLowerCase();
    if (name.startsWith('recording')) return { icon: '🎙️', label: 'Live Recording' };
    if (name.startsWith('kinyarwanda')) return { icon: '🇷🇼', label: 'Kinyarwanda Speech' };
    if (name.endsWith('.mp3') || name.endsWith('.wav') || name.endsWith('.m4a') || name.endsWith('.ogg')) return { icon: '📁', label: 'Uploaded File' };
    return { icon: '🎵', label: 'Audio File' };
  };

  const getLanguageName = (lang) => (lang === 'rw' ? 'Kinyarwanda' : 'English');
  const getLanguageIcon = (lang) => (lang === 'rw' ? '🇷🇼' : '🇬🇧');

  const getAudioDuration = (rec) => {
    if (!rec) return '0:00';
    if (rec.duration) return `${Math.round(rec.duration)}s`;
    const wc = rec.original_text ? rec.original_text.split(/\s+/).length : 0;
    const mins = Math.floor(wc / 150);
    if (mins < 1) return `${Math.floor((wc / 150) * 60)} sec`;
    return `${mins} min`;
  };

  const playAudio = (audioUrl, recordId) => {
    if (playingAudioId === recordId && audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
      setPlayingAudioId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const fullUrl = audioUrl && audioUrl.startsWith('http') ? audioUrl : `${API_URL}${audioUrl}`;
    const audio = new Audio(fullUrl);
    audioRef.current = audio;
    audio.play().then(() => setPlayingAudioId(recordId)).catch((e)=>{ console.error('Audio play error', e); showMessage('error','Audio playback failed'); });
    audio.ontimeupdate = () => setAudioProgress((audio.currentTime / audio.duration) * 100 || 0);
    audio.onended = () => { setPlayingAudioId(null); setAudioProgress(0); };
  };

  const getRoleIcon = (role) => {
    switch(role) {
      case 'director': return '👑';
      case 'secretary': return '📋';
      case 'manager': return '🛡️';
      default: return '👤';
    }
  };

  const getRoleName = (role) => {
    switch(role) {
      case 'director': return 'Director';
      case 'secretary': return 'Secretary';
      case 'manager': return 'Manager';
      default: return 'User';
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.get('/api/admin/stats');
      setStats(response.data.stats);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await api.get('/api/admin/users');
      setUsers(response.data.users || []);
    } catch (err) {
      console.error('Error fetching users:', err);
      setUsers([]);
    }
  };

  const fetchActivity = async () => {
    try {
      const response = await api.get('/api/admin/activity?limit=100');
      setActivity(response.data.logs || []);
    } catch (err) {
      console.error('Error fetching activity:', err);
      setActivity([]);
    }
  };

  const fetchAllTranscriptions = async () => {
    try {
      const response = await api.get('/records');
      setAllTranscriptions(response.data.records || []);
    } catch (err) {
      console.error('Error fetching transcriptions:', err);
      setAllTranscriptions([]);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    
    if (newUser.username.length < 3) {
      showMessage('error', 'Username must be at least 3 characters');
      return;
    }
    if (newUser.password.length < 6) {
      showMessage('error', 'Password must be at least 6 characters');
      return;
    }
    if (!newUser.email.includes('@')) {
      showMessage('error', 'Valid email is required');
      return;
    }

    try {
      const response = await api.post('/api/admin/users', null, {
        params: newUser
      });
      if (response.data.success) {
        showMessage('success', `User "${newUser.username}" created successfully!`);
        setShowCreateUser(false);
        fetchUsers();
        setNewUser({ username: '', email: '', password: '', full_name: '', role: 'secretary', department: '' });
      }
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Error creating user');
    }
  };

  const toggleUserStatus = async (userId, currentStatus) => {
    const userToUpdate = users.find(u => u.id === userId);
    const action = currentStatus ? 'deactivate' : 'activate';
    if (window.confirm(`Are you sure you want to ${action} user "${userToUpdate?.username}"?`)) {
      try {
        await api.put(`/api/admin/users/${userId}/status?is_active=${!currentStatus}`);
        fetchUsers();
        showMessage('success', `User ${action}d successfully!`);
      } catch (err) {
        showMessage('error', 'Error updating status');
      }
    }
  };

  const deleteTranscription = async (recordId, filename) => {
    if (window.confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
      try {
        await api.delete(`/record/${recordId}`);
        await fetchAllTranscriptions();
        showMessage('success', `"${filename}" has been deleted successfully.`);
      } catch (err) {
        console.error('Failed to delete transcription', err);
        showMessage('error', 'Failed to delete transcription');
      }
    }
  };

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setPlayingAudioId(null);
      setAudioProgress(0);
    }
  };

  // Category-specific record getters
  const getEnglishRecords = () => {
    return allTranscriptions.filter(r => r.language_detected === 'en');
  };

  const getKinyarwandaRecords = () => {
    return allTranscriptions.filter(r => r.language_detected === 'rw');
  };

  const getLiveRecordingRecords = () => {
    return allTranscriptions.filter(r => r.filename?.startsWith('recording'));
  };

  const getUploadedRecords = () => {
    return allTranscriptions.filter(r => !r.filename?.startsWith('recording') && !r.filename?.startsWith('kinyarwanda'));
  };

  const getRecordsByCategory = () => {
    switch(selectedCategory) {
      case 'english':
        return getEnglishRecords();
      case 'kinyarwanda':
        return getKinyarwandaRecords();
      case 'live':
        return getLiveRecordingRecords();
      case 'uploaded':
        return getUploadedRecords();
      default:
        return allTranscriptions;
    }
  };

  const viewFullTranscription = (record) => {
    setViewingTranscription(record);
  };

  const closeTranscriptionView = () => {
    setViewingTranscription(null);
  };

  const downloadTranscription = (record) => {
    const data = {
      id: record.id,
      filename: record.filename,
      language: record.language_detected,
      text: record.original_text,
      summary: record.summary_text,
      key_points: record.key_points,
      word_count: record.word_count,
      duration: record.duration,
      created_at: record.created_at,
      user: getUserName(record.user_id)
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${record.filename.replace(/\.[^/.]+$/, '')}_transcription.json`;
    a.click();
    URL.revokeObjectURL(url);
    showMessage('success', 'Transcription downloaded successfully!');
  };

  const downloadCategoryAsDataset = async (category) => {
    let records = [];
    let folderName = '';
    
    switch(category) {
      case 'english':
        records = getEnglishRecords();
        folderName = 'english_dataset';
        break;
      case 'kinyarwanda':
        records = getKinyarwandaRecords();
        folderName = 'kinyarwanda_dataset';
        break;
      case 'live':
        records = getLiveRecordingRecords();
        folderName = 'live_recordings_dataset';
        break;
      case 'uploaded':
        records = getUploadedRecords();
        folderName = 'uploaded_files_dataset';
        break;
      default:
        records = allTranscriptions;
        folderName = 'all_transcriptions_dataset';
    }
    
    if (records.length === 0) {
      showMessage('error', `No records found in ${category} category`);
      return;
    }
    
    setDownloadingCategory(true);
    
    try {
      const zip = new JSZip();
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      
      const metadata = {
        dataset_name: `${category.toUpperCase()} Dataset`,
        created_at: new Date().toISOString(),
        total_records: records.length,
        category: category,
        records_summary: records.map(r => ({
          id: r.id,
          filename: r.filename,
          language: r.language_detected,
          word_count: r.original_text?.split(/\s+/).length || 0,
          created_at: r.created_at,
          user: getUserName(r.user_id)
        }))
      };
      
      zip.file('metadata.json', JSON.stringify(metadata, null, 2));
      
      for (const record of records) {
        const data = {
          id: record.id,
          filename: record.filename,
          language: record.language_detected,
          text: record.original_text,
          summary: record.summary_text,
          key_points: record.key_points,
          word_count: record.word_count,
          duration: record.duration,
          created_at: record.created_at,
          user: getUserName(record.user_id)
        };
        
        const safeFilename = record.filename.replace(/\.[^/.]+$/, '').replace(/[^a-z0-9]/gi, '_');
        zip.file(`${safeFilename}_${record.id}.json`, JSON.stringify(data, null, 2));
      }
      
      const content = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(content);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${folderName}_${timestamp}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      
      showMessage('success', `Dataset with ${records.length} files downloaded successfully!`);
    } catch (err) {
      console.error('Error creating ZIP:', err);
      showMessage('error', 'Failed to create dataset ZIP file');
    } finally {
      setDownloadingCategory(false);
    }
  };

  const exportCategoryToCSV = (category) => {
    let records = [];
    let filename = '';
    
    switch(category) {
      case 'english':
        records = getEnglishRecords();
        filename = 'english_transcriptions';
        break;
      case 'kinyarwanda':
        records = getKinyarwandaRecords();
        filename = 'kinyarwanda_transcriptions';
        break;
      case 'live':
        records = getLiveRecordingRecords();
        filename = 'live_recordings';
        break;
      case 'uploaded':
        records = getUploadedRecords();
        filename = 'uploaded_files';
        break;
      default:
        records = allTranscriptions;
        filename = 'all_transcriptions';
    }
    
    const headers = ['ID', 'Filename', 'Type', 'Language', 'User', 'Words', 'Duration', 'Date', 'Text Preview'];
    const rows = records.map(r => {
      const type = getTranscriptionType(r);
      return [
        r.id,
        `"${r.filename || 'Unknown'}"`,
        type.label,
        getLanguageName(r.language_detected),
        getUserName(r.user_id),
        r.original_text?.split(/\s+/).length || 0,
        getAudioDuration(r),
        new Date(r.created_at).toLocaleString(),
        `"${r.original_text?.substring(0, 100)}..."`
      ];
    });
    
    const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob(["\uFEFF" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showMessage('success', `${category.toUpperCase()} CSV exported successfully!`);
  };

  const categoryStats = {
    total: allTranscriptions.length,
    english: getEnglishRecords().length,
    kinyarwanda: getKinyarwandaRecords().length,
    live: getLiveRecordingRecords().length,
    uploaded: getUploadedRecords().length
  };

  const displayedRecords = getRecordsByCategory();

  const filteredDisplayedRecords = displayedRecords.filter(record => {
    if (filterUser !== 'all' && record.user_id !== parseInt(filterUser)) return false;
    if (filterDate !== 'all') {
      const recordDate = new Date(record.created_at);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 7);
      const monthAgo = new Date(today);
      monthAgo.setMonth(monthAgo.getMonth() - 1);
      
      if (filterDate === 'today' && recordDate < today) return false;
      if (filterDate === 'week' && recordDate < weekAgo) return false;
      if (filterDate === 'month' && recordDate < monthAgo) return false;
    }
    if (filterLanguage !== 'all' && record.language_detected !== filterLanguage) return false;
    if (startDate && new Date(record.created_at) < new Date(startDate)) return false;
    if (endDate && new Date(record.created_at) > new Date(endDate)) return false;
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      return (record.filename || '').toLowerCase().includes(searchLower) ||
             (record.original_text || '').toLowerCase().includes(searchLower);
    }
    return true;
  });

  const clearAllFilters = () => {
    setFilterType('all');
    setFilterUser('all');
    setFilterDate('all');
    setFilterLanguage('all');
    setSearchTerm('');
    setStartDate('');
    setEndDate('');
    showMessage('success', 'Filters cleared!');
  };

  if (loading && !allTranscriptions.length) {
    return (
      <DashboardLayout user={user} onClose={onClose} onLogout={onLogout}>
        <div className="dash-empty">Loading dashboard data...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout user={user} onClose={onClose} onLogout={onLogout}>
      <div className="dash-hero">
        <h1>Welcome back, {(user && (user.full_name || user.username)) || 'Director'}! 👋</h1>
        <p>Manage users, monitor activity, and export data</p>
      </div>

      <div className="dash-header-row">
        <h2 className="dash-section-title" style={{ marginBottom: 0 }}>👑 Overview</h2>
        <button className="dash-btn dash-btn-icon" onClick={fetchAllData} title="Refresh Data">🔄</button>
      </div>

      <div className="dash-stats">
        <div className="dash-stat">
          <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-blue)' }}><DocsIcon /></div></div>
          <div className="dash-stat-value">{totalTranscriptions}</div>
          <div className="dash-stat-label">Transcriptions</div>
        </div>
        <div className="dash-stat">
          <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-green)' }}><UsersIcon /></div></div>
          <div className="dash-stat-value">{totalUsers}</div>
          <div className="dash-stat-label">Users</div>
        </div>
        <div className="dash-stat">
          <div className="dash-stat-value">{totalEnglish}</div>
          <div className="dash-stat-label">🇬🇧 English</div>
        </div>
        <div className="dash-stat">
          <div className="dash-stat-value">{totalKinyarwanda}</div>
          <div className="dash-stat-label">🇷🇼 Kinyarwanda</div>
        </div>
      </div>

      {message && (
        <div className={`dash-alert ${message.type === 'error' ? 'dash-alert-error' : ''}`}>
          {message.type === 'success' ? '✅' : '❌'} {message.text}
        </div>
      )}

      {/* Category Cards */}
      <div className="dash-card">
        <div className="dash-card-header">
          <div>
            <h3>📁 Categories</h3>
            <p>Click a category to filter transcriptions</p>
          </div>
        </div>
        <div className="dash-category-items">
          <div className={`dash-category-item ${selectedCategory === 'all' ? 'active' : ''}`} onClick={() => setSelectedCategory('all')}>
            <span className="dash-category-icon">📊</span>
            <div className="dash-category-info">
              <span className="dash-category-title">All Files</span>
              <span className="dash-category-count">{categoryStats.total}</span>
            </div>
          </div>
          <div className={`dash-category-item ${selectedCategory === 'english' ? 'active' : ''}`} onClick={() => setSelectedCategory('english')}>
            <span className="dash-category-icon">🇬🇧</span>
            <div className="dash-category-info">
              <span className="dash-category-title">English</span>
              <span className="dash-category-count">{categoryStats.english}</span>
            </div>
            <div className="dash-category-actions">
              <button onClick={(e) => { e.stopPropagation(); downloadCategoryAsDataset('english'); }} title="Download as Dataset">📦</button>
              <button onClick={(e) => { e.stopPropagation(); exportCategoryToCSV('english'); }} title="Export CSV">📄</button>
            </div>
          </div>
          <div className={`dash-category-item ${selectedCategory === 'kinyarwanda' ? 'active' : ''}`} onClick={() => setSelectedCategory('kinyarwanda')}>
            <span className="dash-category-icon">🇷🇼</span>
            <div className="dash-category-info">
              <span className="dash-category-title">Kinyarwanda</span>
              <span className="dash-category-count">{categoryStats.kinyarwanda}</span>
            </div>
            <div className="dash-category-actions">
              <button onClick={(e) => { e.stopPropagation(); downloadCategoryAsDataset('kinyarwanda'); }} title="Download as Dataset">📦</button>
              <button onClick={(e) => { e.stopPropagation(); exportCategoryToCSV('kinyarwanda'); }} title="Export CSV">📄</button>
            </div>
          </div>
          <div className={`dash-category-item ${selectedCategory === 'live' ? 'active' : ''}`} onClick={() => setSelectedCategory('live')}>
            <span className="dash-category-icon">🎙️</span>
            <div className="dash-category-info">
              <span className="dash-category-title">Live Recordings</span>
              <span className="dash-category-count">{categoryStats.live}</span>
            </div>
            <div className="dash-category-actions">
              <button onClick={(e) => { e.stopPropagation(); downloadCategoryAsDataset('live'); }} title="Download as Dataset">📦</button>
              <button onClick={(e) => { e.stopPropagation(); exportCategoryToCSV('live'); }} title="Export CSV">📄</button>
            </div>
          </div>
          <div className={`dash-category-item ${selectedCategory === 'uploaded' ? 'active' : ''}`} onClick={() => setSelectedCategory('uploaded')}>
            <span className="dash-category-icon">📁</span>
            <div className="dash-category-info">
              <span className="dash-category-title">Uploaded Files</span>
              <span className="dash-category-count">{categoryStats.uploaded}</span>
            </div>
            <div className="dash-category-actions">
              <button onClick={(e) => { e.stopPropagation(); downloadCategoryAsDataset('uploaded'); }} title="Download as Dataset">📦</button>
              <button onClick={(e) => { e.stopPropagation(); exportCategoryToCSV('uploaded'); }} title="Export CSV">📄</button>
            </div>
          </div>
        </div>
      </div>

      <div className="dash-tabs">
        <button className={`dash-tab ${activeTab === 'transcriptions' ? 'active' : ''}`} onClick={() => setActiveTab('transcriptions')}>
          📜 Transcriptions ({filteredDisplayedRecords.length})
        </button>
        <button className={`dash-tab ${activeTab === 'stats' ? 'active' : ''}`} onClick={() => setActiveTab('stats')}>
          📊 Statistics
        </button>
        <button className={`dash-tab ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>
          👥 User Management ({users.length})
        </button>
        <button className={`dash-tab ${activeTab === 'activity' ? 'active' : ''}`} onClick={() => setActiveTab('activity')}>
          📋 Activity Log
        </button>
      </div>

      {activeTab === 'transcriptions' && (
        <>
          <div className="dash-card">
            <div className="dash-card-header">
              <div>
                <h3>🔍 Filter Transcriptions</h3>
                <p>Narrow down results by user, language, or date</p>
              </div>
            </div>
            <div className="dash-filters-grid">
              <div className="dash-field">
                <label>👤 User</label>
                <select value={filterUser} onChange={(e) => setFilterUser(e.target.value)}>
                  <option value="all">All Users</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>{u.full_name || u.username}</option>
                  ))}
                </select>
              </div>

              <div className="dash-field">
                <label>🌍 Language</label>
                <select value={filterLanguage} onChange={(e) => setFilterLanguage(e.target.value)}>
                  <option value="all">All Languages</option>
                  <option value="en">🇬🇧 English</option>
                  <option value="rw">🇷🇼 Kinyarwanda</option>
                </select>
              </div>

              <div className="dash-field">
                <label>📅 Time Period</label>
                <select value={filterDate} onChange={(e) => setFilterDate(e.target.value)}>
                  <option value="all">All Time</option>
                  <option value="today">Today</option>
                  <option value="week">Last 7 Days</option>
                  <option value="month">Last 30 Days</option>
                </select>
              </div>

              <div className="dash-field">
                <label>🔎 Search</label>
                <input
                  type="text"
                  placeholder="Search by filename or content..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div className="dash-filters-row">
              <div className="dash-field">
                <label>From Date</label>
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div className="dash-field">
                <label>To Date</label>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
              <button className="dash-btn" onClick={clearAllFilters}>
                🗑️ Clear Filters
              </button>
            </div>
          </div>

          <div className="dash-results-summary">
            <span>📊 Found <strong>{filteredDisplayedRecords.length}</strong> transcription(s)</span>
            {selectedCategory !== 'all' && (
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="dash-btn dash-btn-sm" onClick={() => downloadCategoryAsDataset(selectedCategory)} disabled={downloadingCategory}>
                  📦 Download All as Dataset
                </button>
                <button className="dash-btn dash-btn-sm" onClick={() => exportCategoryToCSV(selectedCategory)}>
                  📄 Export All to CSV
                </button>
              </div>
            )}
          </div>

          <div>
            {filteredDisplayedRecords.length === 0 ? (
              <div className="dash-card dash-empty">
                <div style={{ fontSize: 40, marginBottom: 8 }}>📭</div>
                <h3>No transcriptions found</h3>
                <p>Try adjusting your filters or upload new audio</p>
              </div>
            ) : (
              filteredDisplayedRecords.map(record => {
                const type = getTranscriptionType(record);
                const isPlaying = playingAudioId === record.id;
                return (
                  <div key={record.id} className="dash-t-item">
                    <div className="dash-t-header">
                      <div className="dash-t-info">
                        <span title={type.label}>{type.icon} {type.label}</span>
                        <span className={`dash-badge dash-badge-lang ${record.language_detected || 'en'}`}>
                          {getLanguageIcon(record.language_detected)} {getLanguageName(record.language_detected)}
                        </span>
                        <span>👤 {getUserName(record.user_id)}</span>
                      </div>
                      <div className="dash-t-meta">
                        <span>📝 {record.original_text?.split(/\s+/).length || 0} words</span>
                        <span>⏱️ {getAudioDuration(record)}</span>
                        <span>📅 {new Date(record.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div className="dash-t-preview">
                      <strong>📄 {record.filename || 'Untitled'}</strong>
                      <p>{record.original_text?.substring(0, 200)}...</p>
                    </div>

                    {record.audio_url && (
                      <div className="dash-audio-mini">
                        <button
                          className="dash-btn dash-btn-sm"
                          onClick={() => playAudio(record.audio_url, record.id)}
                          title={isPlaying ? 'Pause' : 'Play'}
                        >
                          {isPlaying ? '⏸️' : '▶️'}
                        </button>
                        {isPlaying && (
                          <button className="dash-btn dash-btn-sm" onClick={stopAudio} title="Stop">
                            ⏹️
                          </button>
                        )}
                        <div className="dash-audio-progress">
                          <div className="dash-audio-progress-bar" style={{ width: `${isPlaying ? audioProgress : 0}%` }}></div>
                        </div>
                      </div>
                    )}

                    <div className="dash-t-actions">
                      <button className="dash-btn dash-btn-sm" onClick={() => viewFullTranscription(record)} title="View Full Transcription">
                        👁️ View Full
                      </button>
                      <button className="dash-btn dash-btn-sm" onClick={() => downloadTranscription(record)} title="Download JSON">
                        💾 Download
                      </button>
                      <button className="dash-btn dash-btn-sm dash-btn-danger" onClick={() => deleteTranscription(record.id, record.filename)} title="Delete Permanently">
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      {/* Full Transcription Modal */}
      {viewingTranscription && (
        <div className="dash-modal-overlay" onClick={closeTranscriptionView}>
          <div className="dash-modal" onClick={(e) => e.stopPropagation()}>
            <div className="dash-modal-header">
              <h3>📄 Full Transcription</h3>
              <button className="dash-btn dash-btn-icon dash-btn-sm" onClick={closeTranscriptionView}>×</button>
            </div>
            <div className="dash-modal-body">
              <div className="dash-modal-meta">
                <span>{viewingTranscription.filename}</span>
                <span className={`dash-badge dash-badge-lang ${viewingTranscription.language_detected}`}>
                  {getLanguageIcon(viewingTranscription.language_detected)} {getLanguageName(viewingTranscription.language_detected)}
                </span>
                <span>👤 {getUserName(viewingTranscription.user_id)}</span>
                <span>📅 {new Date(viewingTranscription.created_at).toLocaleString()}</span>
              </div>

              {viewingTranscription.audio_url && (
                <div className="dash-modal-section">
                  <h4>🎵 Audio Playback</h4>
                  <audio controls src={`${API_URL}${viewingTranscription.audio_url}`} style={{ width: '100%' }} />
                </div>
              )}

              <div className="dash-modal-section">
                <h4>📝 Transcription Text</h4>
                <div className="dash-modal-text-content">
                  {viewingTranscription.original_text || 'No text content'}
                </div>
              </div>

              {viewingTranscription.summary_text && (
                <div className="dash-modal-section">
                  <h4>📋 AI Summary</h4>
                  <p style={{ fontSize: 13 }}>{viewingTranscription.summary_text}</p>
                  <div className="dash-summary-stats">
                    <span>Original: {viewingTranscription.original_text?.split(/\s+/).length || 0} words</span>
                    <span>Summary: {viewingTranscription.summary_text.split(/\s+/).length} words</span>
                    <span>Compression: {Math.round((viewingTranscription.summary_text.split(/\s+/).length / (viewingTranscription.original_text?.split(/\s+/).length || 1)) * 100)}%</span>
                  </div>
                </div>
              )}

              {viewingTranscription.key_points && viewingTranscription.key_points.length > 0 && (
                <div className="dash-modal-section">
                  <h4>🔑 Key Points</h4>
                  <ul className="dash-modal-keypoints">
                    {viewingTranscription.key_points.map((point, idx) => (
                      <li key={idx}>
                        <span className="dash-keypoint-num">{idx + 1}</span>
                        <span>{typeof point === 'string' ? point : point.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="dash-modal-footer">
              <button className="dash-btn" onClick={() => downloadTranscription(viewingTranscription)}>
                💾 Download JSON
              </button>
              <button className="dash-btn dash-btn-danger" onClick={() => {
                deleteTranscription(viewingTranscription.id, viewingTranscription.filename);
                closeTranscriptionView();
              }}>
                🗑️ Delete Permanently
              </button>
              <button className="dash-btn dash-btn-primary" onClick={closeTranscriptionView}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stats Tab */}
      {activeTab === 'stats' && stats && (
        <>
          <div className="dash-stats">
            <div className="dash-stat">
              <div className="dash-stat-value">{stats.total_transcriptions || 0}</div>
              <div className="dash-stat-label">📄 Total Transcriptions</div>
            </div>
            <div className="dash-stat">
              <div className="dash-stat-value">{stats.total_users || 0}</div>
              <div className="dash-stat-label">👥 Total Users</div>
            </div>
            <div className="dash-stat">
              <div className="dash-stat-value">{categoryStats.kinyarwanda}</div>
              <div className="dash-stat-label">🇷🇼 Kinyarwanda</div>
            </div>
            <div className="dash-stat">
              <div className="dash-stat-value">{categoryStats.english}</div>
              <div className="dash-stat-label">🇬🇧 English</div>
            </div>
          </div>

          <div className="dash-charts-row">
            <div className="dash-card">
              <div className="dash-card-header"><div><h3>📊 Category Distribution</h3></div></div>
              <div className="dash-distribution">
                <div className="dash-distribution-item">
                  <span>🎙️ Live Recordings</span>
                  <div className="dash-distribution-bar">
                    <div className="dash-distribution-fill" style={{ width: `${(categoryStats.live / Math.max(categoryStats.total, 1)) * 100}%` }}></div>
                  </div>
                  <span>{categoryStats.live}</span>
                </div>
                <div className="dash-distribution-item">
                  <span>📁 Uploaded Files</span>
                  <div className="dash-distribution-bar">
                    <div className="dash-distribution-fill" style={{ width: `${(categoryStats.uploaded / Math.max(categoryStats.total, 1)) * 100}%` }}></div>
                  </div>
                  <span>{categoryStats.uploaded}</span>
                </div>
                <div className="dash-distribution-item">
                  <span>🇬🇧 English</span>
                  <div className="dash-distribution-bar">
                    <div className="dash-distribution-fill" style={{ width: `${(categoryStats.english / Math.max(categoryStats.total, 1)) * 100}%` }}></div>
                  </div>
                  <span>{categoryStats.english}</span>
                </div>
                <div className="dash-distribution-item">
                  <span>🇷🇼 Kinyarwanda</span>
                  <div className="dash-distribution-bar">
                    <div className="dash-distribution-fill" style={{ width: `${(categoryStats.kinyarwanda / Math.max(categoryStats.total, 1)) * 100}%` }}></div>
                  </div>
                  <span>{categoryStats.kinyarwanda}</span>
                </div>
              </div>
            </div>

            <div className="dash-card">
              <div className="dash-card-header"><div><h3>📊 Language Split</h3></div></div>
              <div className="dash-donut-wrap">
                <DonutChart
                  segments={[
                    { label: 'English', value: categoryStats.english, color: 'var(--d-blue)' },
                    { label: 'Kinyarwanda', value: categoryStats.kinyarwanda, color: 'var(--d-purple)' },
                  ]}
                  centerLabel={categoryStats.total}
                  centerSub="Total"
                />
                <div className="dash-donut-legend">
                  <div className="dash-legend-item"><span className="dash-legend-dot" style={{ background: 'var(--d-blue)' }} /> English ({categoryStats.total ? Math.round((categoryStats.english / categoryStats.total) * 100) : 0}%)</div>
                  <div className="dash-legend-item"><span className="dash-legend-dot" style={{ background: 'var(--d-purple)' }} /> Kinyarwanda ({categoryStats.total ? Math.round((categoryStats.kinyarwanda / categoryStats.total) * 100) : 0}%)</div>
                </div>
              </div>
            </div>
          </div>

          <div className="dash-card">
            <div className="dash-card-header"><div><h3>📊 Transcriptions by User</h3></div></div>
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr><th>User</th><th>Transcriptions</th><th>Total Words</th></tr>
                </thead>
                <tbody>
                  {stats.by_user && stats.by_user.length > 0 ? (
                    stats.by_user.map((userStat, idx) => (
                      <tr key={idx}>
                        <td>{userStat.full_name || userStat.username || 'Unknown'}</td>
                        <td>{userStat.count || 0}</td>
                        <td>{userStat.total_words || 0}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan="3" style={{ textAlign: 'center' }}>No data available</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Users Tab */}
      {activeTab === 'users' && (
        <>
          <div className="dash-card">
            <div className="dash-card-header">
              <div>
                <h3>👥 User Management</h3>
                <p>Create, activate, or deactivate user accounts</p>
              </div>
              <button className="dash-btn dash-btn-primary" onClick={() => setShowCreateUser(!showCreateUser)}>
                {showCreateUser ? '✖ Cancel' : '+ Create New User'}
              </button>
            </div>

            {showCreateUser && (
              <form onSubmit={handleCreateUser} style={{ marginTop: 8 }}>
                <div className="dash-form-grid">
                  <div className="dash-field">
                    <label>Username *</label>
                    <input type="text" placeholder="e.g., john_doe" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} required />
                    <small>Minimum 3 characters</small>
                  </div>
                  <div className="dash-field">
                    <label>Email *</label>
                    <input type="email" placeholder="user@example.com" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} required />
                  </div>
                </div>
                <div className="dash-form-grid">
                  <div className="dash-field">
                    <label>Password *</label>
                    <input type="password" placeholder="••••••••" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} required />
                    <small>Minimum 6 characters</small>
                  </div>
                  <div className="dash-field">
                    <label>Full Name</label>
                    <input type="text" placeholder="Full name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} />
                  </div>
                </div>
                <div className="dash-form-grid">
                  <div className="dash-field">
                    <label>Role</label>
                    <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
                      <option value="secretary">📋 Secretary</option>
                      <option value="director">👑 Director</option>
                      <option value="user">👤 Regular User</option>
                    </select>
                  </div>
                  <div className="dash-field">
                    <label>Department</label>
                    <input type="text" placeholder="e.g., IT, HR, Sales" value={newUser.department} onChange={(e) => setNewUser({ ...newUser, department: e.target.value })} />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="submit" className="dash-btn dash-btn-primary">✓ Create User</button>
                  <button type="button" className="dash-btn" onClick={() => setShowCreateUser(false)}>Cancel</button>
                </div>
              </form>
            )}
          </div>

          <div className="dash-card">
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr><th>Username</th><th>Full Name</th><th>Role</th><th>Department</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className={!u.is_active ? 'inactive-row' : ''}>
                      <td>{u.username}</td>
                      <td>{u.full_name || '—'}</td>
                      <td><span className={`dash-badge dash-badge-role ${u.role}`}>{getRoleIcon(u.role)} {getRoleName(u.role)}</span></td>
                      <td>{u.department || '—'}</td>
                      <td><span className={`dash-badge dash-badge-status ${u.is_active ? 'active' : 'inactive'}`}>{u.is_active ? '🟢 Active' : '🔴 Inactive'}</span></td>
                      <td>
                        {u.id !== user?.id && (
                          <button className={`dash-btn dash-btn-sm ${u.is_active ? 'dash-btn-danger' : ''}`} onClick={() => toggleUserStatus(u.id, u.is_active)}>
                            {u.is_active ? '🔒 Deactivate' : '🔓 Activate'}
                          </button>
                        )}
                        {u.id === user?.id && <span style={{ fontSize: 12, color: 'var(--d-text-faint)' }}>(You)</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="dash-stats" style={{ marginTop: 16 }}>
              <div className="dash-stat"><div className="dash-stat-value">{users.length}</div><div className="dash-stat-label">Total Users</div></div>
              <div className="dash-stat"><div className="dash-stat-value">{users.filter(u => u.role === 'director').length}</div><div className="dash-stat-label">Directors</div></div>
              <div className="dash-stat"><div className="dash-stat-value">{users.filter(u => u.role === 'secretary').length}</div><div className="dash-stat-label">Secretaries</div></div>
              <div className="dash-stat"><div className="dash-stat-value">{users.filter(u => u.role === 'user').length}</div><div className="dash-stat-label">Regular Users</div></div>
            </div>
          </div>
        </>
      )}

      {/* Activity Tab */}
      {activeTab === 'activity' && (
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>📋 Activity Log</h3>
              <p>Recent user activities and system events</p>
            </div>
          </div>
          <div className="dash-table-wrap">
            <table className="dash-table">
              <thead>
                <tr><th>Time</th><th>User</th><th>Action</th><th>Details</th></tr>
              </thead>
              <tbody>
                {activity.length > 0 ? (
                  activity.map(log => (
                    <tr key={log.id}>
                      <td>{new Date(log.created_at).toLocaleString()}</td>
                      <td>{log.username || log.full_name || `User ${log.user_id}`}</td>
                      <td><span className="dash-badge">{log.action}</span></td>
                      <td>{log.details || '-'}</td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan="4" style={{ textAlign: 'center' }}>No activity logs available</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default DirectorDashboard;