import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import DirectorDashboard from './DirectorDashboard';
import ManagerDashboard from './ManagerDashboard';
import UserDashboard from './UserDashboard';
import SpeechRecognition from './SpeechRecognition';
import TTSDashboard from './TTSDashboard';
import '../App.css';

const API_URL = 'http://localhost:8000';

function MainApp({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('upload');
  const [isRecording, setIsRecording] = useState(false);
  const [audioFile, setAudioFile] = useState(null);
  const [result, setResult] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [records, setRecords] = useState([]);
  const [error, setError] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState(null);
  const [languageSelected, setLanguageSelected] = useState(false);
  const [playingAudioId, setPlayingAudioId] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordingTimer, setRecordingTimer] = useState(null);
  const [showDirectorDashboard, setShowDirectorDashboard] = useState(false);
  const [showManagerDashboard, setShowManagerDashboard] = useState(false);
  const [showUserDashboard, setShowUserDashboard] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingStage, setProcessingStage] = useState('');
  const [showSpeechRecognition, setShowSpeechRecognition] = useState(false);
  const [showTTSDashboard, setShowTTSDashboard] = useState(false);
  const [historyFilter, setHistoryFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [showWordTimestamps, setShowWordTimestamps] = useState(false);
  const [expandedKeyPoints, setExpandedKeyPoints] = useState({});
  const [showHelper, setShowHelper] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);
  const [showPasswordPanel, setShowPasswordPanel] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ currentPassword: '', newPassword: '', confirmPassword: '' });
  const [passwordMessage, setPasswordMessage] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  // Playback states
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState(null);
  const audioRef = useRef(null);
  const historyScrollRef = useRef(null);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const isDirector = user?.role === 'director' || user?.role === 'admin';
  const isManager = user?.role === 'manager';

  // Helper steps for new users
  const helperSteps = [
    { icon: '🌍', title: 'Select Language', description: 'Choose English or Kinyarwanda first' },
    { icon: '🎙️', title: 'Record or Upload', description: 'Record live audio or upload a file' },
    { icon: '📝', title: 'Get Transcription', description: 'AI generates text, summary & key points' },
    { icon: '💾', title: 'Save & Export', description: 'Save to library or export as PDF/TXT' }
  ];

  const getAuthToken = () => localStorage.getItem('token');

  const api = axios.create({
    baseURL: API_URL,
  });

  api.interceptors.request.use((config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  const handleLogout = async () => {
    if (!window.confirm('Are you sure you want to sign out?')) return;
    try {
      await fetch(`${API_URL}/api/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (err) {
      console.warn('Logout request failed', err);
    }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    onLogout();
  };

  const fetchRecords = useCallback(async () => {
    try {
      const response = await api.get('/records');
      setRecords(response.data.records);
    } catch (err) {
      console.error('Error fetching records:', err);
    }
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  useEffect(() => {
    return () => {
      if (recordingTimer) clearInterval(recordingTimer);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [recordingTimer, audioUrl]);

  useEffect(() => {
    if (languageSelected || audioFile || result) {
      setShowHelper(false);
    }
  }, [languageSelected, audioFile, result]);

  const scrollLeft = () => {
    if (historyScrollRef.current) {
      historyScrollRef.current.scrollBy({ left: -350, behavior: 'smooth' });
    }
  };

  const scrollRight = () => {
    if (historyScrollRef.current) {
      historyScrollRef.current.scrollBy({ left: 350, behavior: 'smooth' });
    }
  };

  const handlePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlaying(false);
      setCurrentTime(0);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e) => {
    const newTime = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const formatPlaybackTime = (seconds) => {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleLanguageSelect = (lang) => {
    setSelectedLanguage(lang);
    setLanguageSelected(true);
    setError(null);
    setShowHelper(false);
    if (audioFile) {
      setAudioFile(null);
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
      }
      const fileInput = document.getElementById('fileInput');
      if (fileInput) fileInput.value = '';
    }
  };

  const startRecording = async () => {
    if (!languageSelected) {
      setError('⚠️ Please select a language (English or Kinyarwanda) first');
      return;
    }
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      setRecordingTime(0);
      
      const timer = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      setRecordingTimer(timer);
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };
      
      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const file = new File([audioBlob], 'recording.wav', { type: 'audio/wav' });
        setAudioFile(file);
        const url = URL.createObjectURL(audioBlob);
        setAudioUrl(url);
        setError(null);
        if (recordingTimer) clearInterval(recordingTimer);
        setRecordingTime(0);
      };
      
      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      setError('Microphone access denied. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  const handleFileChange = (e) => {
    if (!languageSelected) {
      setError('⚠️ Please select a language (English or Kinyarwanda) first');
      e.target.value = '';
      return;
    }
    
    const file = e.target.files[0];
    if (file) {
      if (file.size > 200 * 1024 * 1024) {
        setError('File too large. Maximum size is 200MB.');
        e.target.value = '';
        return;
      }
      setAudioFile(file);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      const url = URL.createObjectURL(file);
      setAudioUrl(url);
      setError(null);
      setResult(null);
      setShowHelper(false);
    }
  };

  const handleSubmit = async () => {
    if (!audioFile) {
      setError('Please select or record an audio file');
      return;
    }
    
    if (!languageSelected || !selectedLanguage) {
      setError('⚠️ Please select a language first');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setProcessingProgress(0);
    setProcessingStage('Preprocessing audio...');
    
    const formData = new FormData();
    formData.append('file', audioFile);
    formData.append('language', selectedLanguage);

    try {
      const stages = [
        { progress: 10, text: '🎤 Loading audio file...' },
        { progress: 25, text: '🔊 Preprocessing audio (noise reduction)...' },
        { progress: 40, text: '🎙️ Transcribing with AI...' },
        { progress: 60, text: '📝 Formatting text with punctuation...' },
        { progress: 75, text: '🤖 Generating smart summary...' },
        { progress: 90, text: '🔑 Extracting key points...' },
      ];
      
      let stageIndex = 0;
      const progressInterval = setInterval(() => {
        if (stageIndex < stages.length) {
          const stage = stages[stageIndex];
          setProcessingProgress(stage.progress);
          setProcessingStage(stage.text);
          stageIndex++;
        } else {
          setProcessingProgress(95);
          setProcessingStage('✨ Finalizing results...');
        }
      }, 2000);
      
      const response = await api.post('/upload', formData);
      clearInterval(progressInterval);
      setProcessingProgress(100);
      setProcessingStage('✅ Complete!');
      
      if (response.data.success) {
        setResult(response.data);
        fetchRecords();
        setAudioFile(null);
        if (audioUrl) {
          URL.revokeObjectURL(audioUrl);
          setAudioUrl(null);
        }
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';
        
        setTimeout(() => {
          setProcessingStage('');
        }, 1500);
      } else {
        setError(response.data.error || 'Transcription failed');
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.error || 'Error processing audio. Please try again.');
    } finally {
      setTimeout(() => {
        setIsProcessing(false);
        setProcessingProgress(0);
        setProcessingStage('');
      }, 1000);
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm('Are you sure you want to delete this record? This action cannot be undone.')) {
      try {
        await api.delete(`/record/${id}`);
        fetchRecords();
        if (result && result.record_id === id) {
          setResult(null);
        }
      } catch (err) {
        console.error('Delete error:', err);
        setError('Failed to delete record');
      }
    }
  };

  const exportAsPDF = async (recordId) => {
    try {
      const response = await api.get(`/export/pdf/${recordId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transcription_${recordId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error exporting PDF. Please try again.');
    }
  };

  const exportAsTXT = async (recordId) => {
    try {
      const response = await api.get(`/export/txt/${recordId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transcription_${recordId}.txt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error exporting TXT. Please try again.');
    }
  };

  const playHistoryAudio = (audioUrl, recordId) => {
    if (playingAudioId === recordId) {
      if (window.currentAudio) {
        window.currentAudio.pause();
        window.currentAudio = null;
      }
      setPlayingAudioId(null);
    } else {
      if (window.currentAudio) {
        window.currentAudio.pause();
      }
      const fullUrl = audioUrl.startsWith('http') ? audioUrl : `${API_URL}${audioUrl}`;
      const audio = new Audio(fullUrl);
      window.currentAudio = audio;
      audio.play();
      setPlayingAudioId(recordId);
      audio.onended = () => {
        setPlayingAudioId(null);
        window.currentAudio = null;
      };
      audio.onerror = () => {
        setPlayingAudioId(null);
        window.currentAudio = null;
        setError('Failed to play audio');
      };
    }
  };

  const getImportanceColor = (importance) => {
    switch(importance) {
      case 'high': return '#dc2626';
      case 'medium': return '#f59e0b';
      default: return '#10b981';
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDuration = (durationStr) => {
    if (!durationStr) return '—';
    return durationStr;
  };

  const getFilteredRecords = () => {
    let filtered = records;
    
    if (historyFilter === 'uploaded') {
      filtered = filtered.filter(r => !r.filename?.startsWith('recording') && !r.filename?.startsWith('kinyarwanda'));
    } else if (historyFilter === 'recorded') {
      filtered = filtered.filter(r => r.filename?.startsWith('recording') || r.filename?.startsWith('kinyarwanda'));
    }
    
    if (languageFilter === 'en') {
      filtered = filtered.filter(r => r.language_detected === 'en');
    } else if (languageFilter === 'rw') {
      filtered = filtered.filter(r => r.language_detected === 'rw');
    }
    
    return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  };

  const getRecordIcon = (record) => {
    if (record.filename?.startsWith('recording')) return '🎙️';
    if (record.filename?.startsWith('kinyarwanda')) return '🇷🇼';
    return '📁';
  };

  const toggleKeyPointExpand = (pointNumber) => {
    setExpandedKeyPoints(prev => ({
      ...prev,
      [pointNumber]: !prev[pointNumber]
    }));
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    const notification = document.createElement('div');
    notification.className = 'copy-notification';
    notification.textContent = '✅ Copied to clipboard!';
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 2000);
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (!passwordForm.currentPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
      setPasswordMessage('Please complete all password fields');
      return;
    }
    if (passwordForm.newPassword.length < 6) {
      setPasswordMessage('New password must be at least 6 characters');
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordMessage('New passwords do not match');
      return;
    }

    setPasswordLoading(true);
    setPasswordMessage('');

    try {
      const response = await api.post('/api/auth/password/change', {
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword
      });

      if (response.data.success) {
        setPasswordMessage(response.data.message || 'Password changed successfully');
        setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
        setShowPasswordPanel(false);
      } else {
        setPasswordMessage(response.data.detail || 'Unable to change password');
      }
    } catch (err) {
      console.error('Password change error:', err);
      setPasswordMessage(err.response?.data?.detail || 'Unable to change password');
    } finally {
      setPasswordLoading(false);
    }
  };

  const filteredRecords = getFilteredRecords();

  // Show TTS Dashboard
  if (showTTSDashboard) {
    return <TTSDashboard user={user} onBack={() => setShowTTSDashboard(false)} />;
  }

  if (showSpeechRecognition) {
    return <SpeechRecognition user={user} onBack={() => setShowSpeechRecognition(false)} />;
  }

  if (showDirectorDashboard) {
    return <DirectorDashboard user={user} onClose={() => setShowDirectorDashboard(false)} onLogout={handleLogout} />;
  }

  if (showManagerDashboard) {
    return <ManagerDashboard user={user} onClose={() => setShowManagerDashboard(false)} onLogout={handleLogout} />;
  }

  if (showUserDashboard) {
    return <UserDashboard user={user} onClose={() => setShowUserDashboard(false)} onLogout={handleLogout} />;
  }

  return (
    <div className="app">
      {/* Welcome Banner */}
      {!languageSelected && !audioFile && !result && (
        <div className="welcome-banner">
          <div className="welcome-content">
            <div className="welcome-icon">📚</div>
            <div className="welcome-text">
              <h2>Welcome to EVA</h2>
              <p>Turn your audio into text, summaries, and key points with AI</p>
            </div>
          </div>
          <div className="quick-tips">
            <span className="tip">💡 Select a language first</span>
            <span className="tip">🎙️ Record or upload audio</span>
            <span className="tip">📝 Get AI-powered transcription</span>
            <span className="tip">🔊 Convert text to speech</span>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">🎙️</span>
            <span className="logo-text">EVA</span>
          </div>
          <p className="tagline">Professional Audio Transcription & AI Summarization</p>
        </div>
        <div className="header-right">
          <div className="user-info">
            <div className="user-avatar">
              {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.full_name || user?.username}</span>
              <span className={`user-role-badge ${isDirector ? 'director' : 'secretary'}`}>
                {isDirector ? '👑 Director' : '📋 Secretary'}
              </span>
            </div>
            {isDirector && (
              <button 
                onClick={() => {
                  // Open appropriate dashboard based on role
                  if (isDirector) setShowDirectorDashboard(true);
                  else if (isManager) setShowManagerDashboard(true);
                  else setShowUserDashboard(true);
                }}
                className="director-btn" 
                title="Director Dashboard"
              >
                👑
              </button>
            )}
            <button onClick={onLogout} className="logout-btn" title="Logout">
              🚪
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="tabs-container">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'upload' ? 'active' : ''}`} 
            onClick={() => setActiveTab('upload')}
          >
            <span className="tab-icon">🎤</span>
            <span className="tab-text">Transcribe</span>
          </button>
          <button 
            className={`tab ${activeTab === 'history' ? 'active' : ''}`} 
            onClick={() => setActiveTab('history')}
          >
            <span className="tab-icon">📜</span>
            <span className="tab-text">Library</span>
            {records.length > 0 && <span className="tab-badge">{records.length}</span>}
          </button>
          <button 
            className={`tab ${activeTab === 'speech' ? 'active' : ''}`} 
            onClick={() => setShowSpeechRecognition(true)}
          >
            <span className="tab-icon">🎙️</span>
            <span className="tab-text">Live Speech</span>
          </button>
          <button 
            className={`tab ${activeTab === 'tts' ? 'active' : ''}`} 
            onClick={() => setShowTTSDashboard(true)}
          >
            <span className="tab-icon">🔊</span>
            <span className="tab-text">Text-to-Speech</span>
          </button>
        </div>
      </div>

      <div className="password-panel-card">
        <div className="password-panel-head">
          <div>
            <h3>Security</h3>
            <p>Change your password anytime and keep your account protected.</p>
          </div>
          <button type="button" className="password-panel-toggle" onClick={() => setShowPasswordPanel((prev) => !prev)}>
            {showPasswordPanel ? 'Hide' : 'Change Password'}
          </button>
        </div>

        {showPasswordPanel && (
          <form className="password-panel-form" onSubmit={handlePasswordChange}>
            <div className="form-group">
              <label>Current Password</label>
              <div className="input-icon">
                <span className="icon">🔒</span>
                <input
                  type={showCurrentPassword ? 'text' : 'password'}
                  value={passwordForm.currentPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                  placeholder="Enter your current password"
                  required
                  disabled={passwordLoading}
                />
                <button type="button" className="password-toggle-btn" onClick={() => setShowCurrentPassword((prev) => !prev)}>
                  {showCurrentPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>New Password</label>
              <div className="input-icon">
                <span className="icon">🔒</span>
                <input
                  type={showNewPassword ? 'text' : 'password'}
                  value={passwordForm.newPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                  placeholder="Choose a new password"
                  required
                  disabled={passwordLoading}
                />
                <button type="button" className="password-toggle-btn" onClick={() => setShowNewPassword((prev) => !prev)}>
                  {showNewPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <div className="input-icon">
                <span className="icon">🔒</span>
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                  placeholder="Confirm your new password"
                  required
                  disabled={passwordLoading}
                />
                <button type="button" className="password-toggle-btn" onClick={() => setShowConfirmPassword((prev) => !prev)}>
                  {showConfirmPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {passwordMessage && <div className={passwordMessage.toLowerCase().includes('success') ? 'success-message' : 'error-message'}>{passwordMessage}</div>}

            <button type="submit" className="auth-btn" disabled={passwordLoading}>
              {passwordLoading ? 'Updating password...' : 'Change Password'}
            </button>
          </form>
        )}
      </div>

      <div className="main-content">
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <>
            {/* Helper Steps */}
            {showHelper && !languageSelected && (
              <div className="helper-steps">
                <div className="helper-header">
                  <span className="helper-icon">🤖</span>
                  <span className="helper-title">How to get started</span>
                  <button className="helper-close" onClick={() => setShowHelper(false)}>✕</button>
                </div>
                <div className="steps-container">
                  {helperSteps.map((step, index) => (
                    <div key={index} className={`step-item ${index === currentStep ? 'active' : ''}`}>
                      <div className="step-number">{index + 1}</div>
                      <div className="step-icon">{step.icon}</div>
                      <div className="step-content">
                        <div className="step-title">{step.title}</div>
                        <div className="step-desc">{step.description}</div>
                      </div>
                      {index < helperSteps.length - 1 && <div className="step-arrow">→</div>}
                    </div>
                  ))}
                </div>
                <div className="helper-nav">
                  <button className="helper-prev" onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}>◀</button>
                  <span className="helper-indicators">
                    {helperSteps.map((_, i) => (
                      <span key={i} className={`dot ${i === currentStep ? 'active' : ''}`} />
                    ))}
                  </span>
                  <button className="helper-next" onClick={() => setCurrentStep(Math.min(helperSteps.length - 1, currentStep + 1))}>▶</button>
                </div>
              </div>
            )}

            {/* Audio Input Card */}
            <div className="card input-card">
              <div className="card-header">
                <h3>🎧 Audio Input</h3>
                <p className="card-subtitle">Select your language, then record or upload audio</p>
              </div>
              
              {/* Language Selector */}
              <div className="language-selector-primary">
                <div className="language-selector-header">
                  <span className="required-icon">⚠️</span>
                  <span className="required-text">Step 1: Select Your Language FIRST (Required)</span>
                </div>
                <div className="language-options-primary">
                  <button 
                    className={`lang-option-primary ${selectedLanguage === 'en' ? 'selected' : ''}`}
                    onClick={() => handleLanguageSelect('en')}
                  >
                    <span className="lang-flag">🇬🇧</span>
                    <span className="lang-name">English</span>
                    {selectedLanguage === 'en' && <span className="check-icon">✓</span>}
                  </button>
                  <button 
                    className={`lang-option-primary ${selectedLanguage === 'rw' ? 'selected' : ''}`}
                    onClick={() => handleLanguageSelect('rw')}
                  >
                    <span className="lang-flag">🇷🇼</span>
                    <span className="lang-name">Kinyarwanda</span>
                    {selectedLanguage === 'rw' && <span className="check-icon">✓</span>}
                  </button>
                </div>
                {!languageSelected && (
                  <p className="language-warning">⚠️ You MUST select a language before recording or uploading audio</p>
                )}
                {languageSelected && (
                  <p className="language-confirm">✅ Language selected: {selectedLanguage === 'en' ? 'English' : 'Kinyarwanda'} - You can now record or upload</p>
                )}
              </div>

              {/* Input Methods */}
              <div className="input-methods">
                <div className="method recording-method">
                  <div className="method-icon">🎙️</div>
                  <h4>Live Recording</h4>
                  <p className="method-hint">Record directly from your microphone</p>
                  {!isRecording ? (
                    <button 
                      onClick={startRecording} 
                      className={`btn-record ${!languageSelected ? 'disabled' : ''}`}
                      disabled={!languageSelected}
                    >
                      <span className="btn-icon">🔴</span>
                      Start Recording
                    </button>
                  ) : (
                    <>
                      <div className="recording-timer">
                        <span className="timer-icon">⏱️</span>
                        {formatTime(recordingTime)}
                      </div>
                      <button onClick={stopRecording} className="btn-stop">
                        <span className="btn-icon">⏹️</span>
                        Stop Recording
                      </button>
                      <div className="recording-wave">
                        <span></span><span></span><span></span><span></span><span></span>
                      </div>
                    </>
                  )}
                  {!languageSelected && (
                    <p className="disabled-hint">🔒 Select language first to enable recording</p>
                  )}
                </div>

                <div className="method-divider">
                  <span>OR</span>
                </div>

                <div className="method upload-method">
                  <div className="method-icon">📁</div>
                  <h4>Upload File</h4>
                  <p className="method-hint">Upload existing audio files</p>
                  <label htmlFor="fileInput" className={`upload-label ${!languageSelected ? 'disabled' : ''}`}>
                    Choose Audio File
                  </label>
                  <input 
                    id="fileInput" 
                    type="file" 
                    accept="audio/*" 
                    onChange={handleFileChange} 
                    disabled={!languageSelected}
                  />
                  <p className="hint">MP3, WAV, M4A, OGG • Unlimited length supported (Max 200MB)</p>
                  {!languageSelected && (
                    <p className="disabled-hint">🔒 Select language first to enable upload</p>
                  )}
                </div>
              </div>

              {/* Selected File Preview */}
              {audioFile && audioUrl && (
                <div className="selected-file-preview">
                  <div className="file-info">
                    <div className="file-icon">🎵</div>
                    <div className="file-details">
                      <div className="file-name">{audioFile.name}</div>
                      <div className="file-meta">
                        <span className="file-size">{(audioFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                        <span className="file-type">{audioFile.type?.split('/')[1]?.toUpperCase() || 'AUDIO'}</span>
                      </div>
                    </div>
                    <button onClick={() => {
                      setAudioFile(null);
                      if (audioUrl) URL.revokeObjectURL(audioUrl);
                      setAudioUrl(null);
                      const fileInput = document.getElementById('fileInput');
                      if (fileInput) fileInput.value = '';
                    }} className="remove-file" title="Remove file">✕</button>
                  </div>
                  
                  <div className="audio-playback-container">
                    <div className="file-waveform">
                      <span></span><span></span><span></span><span></span><span></span><span></span><span></span>
                    </div>
                    <div className="audio-controls">
                      <button className="playback-btn" onClick={handlePlayPause} title={isPlaying ? 'Pause' : 'Play'}>
                        {isPlaying ? '⏸️' : '▶️'}
                      </button>
                      <button className="playback-btn stop" onClick={handleStop} title="Stop">⏹️</button>
                      <div className="playback-progress">
                        <input
                          type="range"
                          min="0"
                          max={duration || 0}
                          value={currentTime}
                          onChange={handleSeek}
                          step="0.01"
                        />
                      </div>
                      <div className="playback-time">
                        {formatPlaybackTime(currentTime)} / {formatPlaybackTime(duration)}
                      </div>
                    </div>
                  </div>
                  
                  <audio
                    ref={audioRef}
                    src={audioUrl}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={handleLoadedMetadata}
                    onEnded={() => setIsPlaying(false)}
                    style={{ display: 'none' }}
                  />
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div className="error-message">
                  <span className="error-icon">⚠️</span>
                  <span className="error-text">{error}</span>
                  <button className="error-close" onClick={() => setError(null)}>✕</button>
                </div>
              )}

              {/* Processing Progress */}
              {isProcessing && (
                <div className="processing-container">
                  <div className="processing-bar">
                    <div className="processing-progress" style={{ width: `${processingProgress}%` }}>
                      <span className="processing-percent">{processingProgress}%</span>
                    </div>
                  </div>
                  <div className="processing-stage">
                    <span className="stage-icon">
                      {processingProgress < 30 ? '🎤' : processingProgress < 60 ? '🤖' : processingProgress < 90 ? '📝' : '✨'}
                    </span>
                    <span className="stage-text">{processingStage}</span>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              {audioFile && !isProcessing && languageSelected && (
                <button onClick={handleSubmit} className="btn-submit">
                  <span className="btn-icon">✨</span>
                  Transcribe Audio
                </button>
              )}
            </div>

            {/* Results */}
            {result && (
              <div className="results-container">
                <div className="results-header">
                  <h3>📊 Transcription Results</h3>
                  <div className="results-actions">
                    <button className="btn-clear-results" onClick={() => setResult(null)}>✕ Clear</button>
                  </div>
                </div>

                {/* Audio Playback */}
                {result.audio_url && (
                  <div className="card playback-card">
                    <div className="card-header-mini">
                      <h4>▶️ Audio Playback</h4>
                      <div className="audio-info">
                        <span className="duration-badge">{formatDuration(result.text_metrics?.duration)}</span>
                        {result.text_metrics?.chunks_processed > 1 && (
                          <span className="chunks-badge">📦 {result.text_metrics.chunks_processed} chunks</span>
                        )}
                        <button 
                          className="copy-btn-mini"
                          onClick={() => copyToClipboard(result.text)}
                          title="Copy transcription"
                        >
                          📋 Copy
                        </button>
                      </div>
                    </div>
                    <audio controls className="audio-player" src={`${API_URL}${result.audio_url}`} />
                  </div>
                )}

                {/* Stats Grid */}
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-icon">📝</div>
                    <div className="stat-value">{result.text_metrics?.word_count || 0}</div>
                    <div className="stat-label">Words</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">⏱️</div>
                    <div className="stat-value">{result.text_metrics?.duration || '0'}</div>
                    <div className="stat-label">Duration</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">📊</div>
                    <div className="stat-value">{result.summary_metrics?.compression || '0%'}</div>
                    <div className="stat-label">Compression</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon">💬</div>
                    <div className="stat-value">{result.text_metrics?.sentence_count || 0}</div>
                    <div className="stat-label">Sentences</div>
                  </div>
                </div>

                {/* Full Transcription */}
                <div className="card transcription-card">
                  <div className="card-header-with-badge">
                    <h3>📝 Full Transcription</h3>
                    <div className={`language-badge ${selectedLanguage}`}>
                      {selectedLanguage === 'rw' ? '🇷🇼 Kinyarwanda' : '🇬🇧 English'}
                    </div>
                  </div>
                  <div className="text-content">
                    {result.text?.split('\n\n').map((paragraph, idx) => (
                      <p key={idx} className="paragraph">{paragraph}</p>
                    ))}
                  </div>
                  <div className="transcription-footer">
                    <button 
                      className="copy-transcription-btn"
                      onClick={() => copyToClipboard(result.text)}
                    >
                      📋 Copy Full Transcription
                    </button>
                    <button 
                      className="tts-btn-mini"
                      onClick={() => setShowTTSDashboard(true)}
                      title="Convert to Speech"
                    >
                      🔊 Text-to-Speech
                    </button>
                  </div>
                </div>

                {/* AI Summary */}
                <div className="card summary-card">
                  <div className="card-header-with-badges">
                    <h3>📋 AI Summary</h3>
                    <div className="badge-group">
                      <span className="badge purple">
                        {result.summary_metrics?.type === 'full_summary' ? '📖 Full Summary' :
                         result.summary_metrics?.type === 'detailed_summary' ? '📖 Detailed Summary' :
                         result.summary_metrics?.type === 'standard_summary' ? '📘 Standard Summary' :
                         result.summary_metrics?.type === 'concise_summary' ? '📙 Concise Summary' :
                         result.summary_metrics?.type === 'executive_summary' ? '📊 Executive Summary' :
                         result.summary_metrics?.type === 'ultra_summary' ? '🎯 Ultra Summary' :
                         '🎯 AI Summary'}
                      </span>
                      <span className="badge green">📉 {result.summary_metrics?.compression || '0%'}</span>
                      <span className="badge blue">🎯 {result.summary_metrics?.target_percent || 35}% summary</span>
                    </div>
                  </div>
                  <div className="summary-content">
                    <p>{result.summary || result.text?.substring(0, 300) || 'No summary available'}</p>
                  </div>
                  <div className="summary-footer">
                    <div className="summary-stats">
                      <div className="summary-stat">
                        <span className="stat-icon">📝</span>
                        <span className="stat-text">Original: {result.summary_metrics?.original_words || result.text_metrics?.word_count || 0} words</span>
                      </div>
                      <div className="summary-stat">
                        <span className="stat-icon">✨</span>
                        <span className="stat-text">Summary: {result.summary_metrics?.summary_words || 0} words</span>
                      </div>
                    </div>
                    <button 
                      className="copy-summary-btn"
                      onClick={() => copyToClipboard(result.summary)}
                    >
                      📋 Copy Summary
                    </button>
                  </div>
                </div>

                {/* Key Points */}
                <div className="card keypoints-card">
                  <h3>🔑 Key Points</h3>
                  <div className="key-points-list">
                    {result.key_points && result.key_points.length > 0 ? (
                      result.key_points.map((point) => (
                        <div key={point.number} className="key-point" style={{ borderLeftColor: getImportanceColor(point.importance) }}>
                          <div className="key-point-header">
                            <span className="key-point-number">{point.number}</span>
                            <span className="key-point-icon">{point.icon}</span>
                            <span className="key-point-importance" style={{ color: getImportanceColor(point.importance) }}>
                              {point.importance?.toUpperCase() || 'MEDIUM'} PRIORITY
                            </span>
                            <button 
                              className="expand-point-btn"
                              onClick={() => toggleKeyPointExpand(point.number)}
                            >
                              {expandedKeyPoints[point.number] ? '−' : '+'}
                            </button>
                          </div>
                          <p className={`key-point-text ${expandedKeyPoints[point.number] ? 'expanded' : ''}`}>
                            {point.text}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="no-keypoints">No key points extracted</p>
                    )}
                  </div>
                </div>

                {/* Word Timestamps */}
                {result.word_timestamps && result.word_timestamps.length > 0 && (
                  <div className="card timestamps-card">
                    <div className="timestamps-header">
                      <h3>⏱️ Word Timestamps</h3>
                      <button 
                        className="toggle-timestamps-btn"
                        onClick={() => setShowWordTimestamps(!showWordTimestamps)}
                      >
                        {showWordTimestamps ? 'Hide' : 'Show'} Timestamps
                      </button>
                    </div>
                    {showWordTimestamps && (
                      <div className="timestamps-grid">
                        {result.word_timestamps.map((word, idx) => (
                          <div key={idx} className="timestamp-item">
                            <span className="timestamp-word">{word.word}</span>
                            <span className="timestamp-time">{word.start}s - {word.end}s</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Export Options */}
                {result.record_id && (
                  <div className="card export-card">
                    <h3>📄 Export Options</h3>
                    <p className="export-hint">Download your transcription in multiple formats</p>
                    <div className="export-buttons">
                      <button className="btn-export pdf" onClick={() => exportAsPDF(result.record_id)}>
                        📄 Export as PDF
                      </button>
                      <button className="btn-export txt" onClick={() => exportAsTXT(result.record_id)}>
                        📝 Export as TXT
                      </button>
                      <button 
                        className="btn-export copy-all"
                        onClick={() => {
                          const exportText = `TRANSCRIPTION:\n${result.text}\n\nSUMMARY:\n${result.summary}\n\nKEY POINTS:\n${result.key_points.map(p => `${p.number}. ${p.text}`).join('\n')}`;
                          copyToClipboard(exportText);
                        }}
                      >
                        📋 Copy All
                      </button>
                      <button 
                        className="btn-export tts"
                        onClick={() => setShowTTSDashboard(true)}
                      >
                        🔊 Text-to-Speech
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="history-section">
            {/* Filters */}
            <div className="history-filters">
              <button 
                className={`filter-btn ${historyFilter === 'all' && languageFilter === 'all' ? 'active' : ''}`}
                onClick={() => { setHistoryFilter('all'); setLanguageFilter('all'); }}
              >
                📁 All Files ({records.length})
              </button>
              <button 
                className={`filter-btn ${historyFilter === 'uploaded' && languageFilter === 'all' ? 'active' : ''}`}
                onClick={() => { setHistoryFilter('uploaded'); setLanguageFilter('all'); }}
              >
                📤 Uploaded ({records.filter(r => !r.filename?.startsWith('recording') && !r.filename?.startsWith('kinyarwanda')).length})
              </button>
              <button 
                className={`filter-btn ${historyFilter === 'recorded' && languageFilter === 'all' ? 'active' : ''}`}
                onClick={() => { setHistoryFilter('recorded'); setLanguageFilter('all'); }}
              >
                🎙️ Recorded ({records.filter(r => r.filename?.startsWith('recording') || r.filename?.startsWith('kinyarwanda')).length})
              </button>
              <div className="filter-divider"></div>
              <button 
                className={`filter-btn ${languageFilter === 'en' ? 'active' : ''}`}
                onClick={() => setLanguageFilter(languageFilter === 'en' ? 'all' : 'en')}
              >
                🇬🇧 English ({records.filter(r => r.language_detected === 'en').length})
              </button>
              <button 
                className={`filter-btn ${languageFilter === 'rw' ? 'active' : ''}`}
                onClick={() => setLanguageFilter(languageFilter === 'rw' ? 'all' : 'rw')}
              >
                🇷🇼 Kinyarwanda ({records.filter(r => r.language_detected === 'rw').length})
              </button>
            </div>

            <div className="history-header">
              <h4>📚 Your Audio Library</h4>
              <p className="history-hint">Browse, play, and manage your transcriptions</p>
            </div>

            {/* Scroll Buttons */}
            <div className="scroll-buttons">
              <button className="scroll-btn" onClick={scrollLeft} title="Scroll Left">◀</button>
              <button className="scroll-btn" onClick={scrollRight} title="Scroll Right">▶</button>
            </div>

            {/* History List */}
            <div className="history-list" ref={historyScrollRef}>
              {filteredRecords.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📭</div>
                  <h3>No files found</h3>
                  <p>Try changing filters or upload new audio</p>
                </div>
              ) : (
                filteredRecords.map(record => (
                  <div key={record.id} className="history-item">
                    <div className="history-item-header">
                      <div className="history-item-info">
                        <span className={`history-lang-badge ${record.language_detected === 'rw' ? 'rw' : 'en'}`}>
                          {record.language_detected === 'rw' ? '🇷🇼 Kinyarwanda' : '🇬🇧 English'}
                        </span>
                        <span className="history-icon">{getRecordIcon(record)}</span>
                        <span className="history-filename" title={record.filename}>
                          {record.filename?.length > 30 ? record.filename.substring(0, 27) + '...' : record.filename}
                        </span>
                      </div>
                      <div className="history-meta">
                        <span>📅 {new Date(record.created_at).toLocaleDateString()}</span>
                        <span>📝 {record.word_count || 0} words</span>
                      </div>
                    </div>
                    
                    <div className="history-preview">
                      {record.original_text?.substring(0, 100)}...
                    </div>
                    
                    <div className="history-actions">
                      {record.audio_url && (
                        <button 
                          className={`action-btn play ${playingAudioId === record.id ? 'playing' : ''}`}
                          onClick={() => playHistoryAudio(record.audio_url, record.id)}
                          title={playingAudioId === record.id ? 'Stop' : 'Play Audio'}
                        >
                          {playingAudioId === record.id ? '⏸️' : '▶️'}
                        </button>
                      )}
                      <button className="action-btn view" onClick={() => {
                        setResult({
                          record_id: record.id,
                          text: record.original_text,
                          summary: record.summary_text,
                          key_points: record.key_points,
                          text_metrics: { word_count: record.word_count, duration: record.duration },
                          audio_url: record.audio_url,
                          language: record.language_detected
                        });
                        setActiveTab('upload');
                      }} title="View">👁️</button>
                      <button className="action-btn pdf" onClick={() => exportAsPDF(record.id)} title="Export PDF">📄</button>
                      <button className="action-btn txt" onClick={() => exportAsTXT(record.id)} title="Export TXT">📝</button>
                      <button className="action-btn tts" onClick={() => setShowTTSDashboard(true)} title="Text-to-Speech">🔊</button>
                      <button className="action-btn delete" onClick={() => handleDelete(record.id)} title="Delete">🗑️</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default MainApp;
