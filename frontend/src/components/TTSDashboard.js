import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import '../App.css';

const API_URL = 'http://localhost:8000';

function TTSDashboard({ user, onBack }) {
  const [activeTab, setActiveTab] = useState('synthesize');
  const [documents, setDocuments] = useState([]);
  const [voices, setVoices] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [manualText, setManualText] = useState('');
  const [rewrittenText, setRewrittenText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [voiceName, setVoiceName] = useState('');
  const [voiceLanguage, setVoiceLanguage] = useState('rw');
  const [voiceFile, setVoiceFile] = useState(null);
  const [registeringVoice, setRegisteringVoice] = useState(false);
  const [documentFile, setDocumentFile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showHelper, setShowHelper] = useState(true);
  const [genderFilter, setGenderFilter] = useState('all');
  const [ageFilter, setAgeFilter] = useState('all');
  const [isRewriting, setIsRewriting] = useState(false);
  const [textStats, setTextStats] = useState({
    words: 0,
    characters: 0,
    sentences: 0,
    paragraphs: 0
  });
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [previewingVoice, setPreviewingVoice] = useState(null);
  const [voiceRecording, setVoiceRecording] = useState(false);
  const [voiceRecordingSeconds, setVoiceRecordingSeconds] = useState(0);
  const textareaRef = useRef(null);
  const previewAudioRef = useRef(null);
  const voiceMediaRecorderRef = useRef(null);
  const voiceChunksRef = useRef([]);
  const voiceStreamRef = useRef(null);
  const voiceTimerRef = useRef(null);

  const helperSteps = [
    { icon: '📄', title: 'Upload Document or Type Text', description: 'Upload a document or type your text directly' },
    { icon: '🔄', title: 'Rewrite Content', description: 'System rewrites text for better readability' },
    { icon: '🎤', title: 'Select Voice', description: 'Choose a voice from our Kinyarwanda voices' },
    { icon: '🔊', title: 'Generate Speech', description: 'AI converts text to natural Kinyarwanda speech' }
  ];

  const voiceCategories = {
    'female': { label: '👩 Women', icon: '👩' },
    'male': { label: '👨 Men', icon: '👨' },
    'child': { label: '🧒 Children', icon: '🧒' },
    'elderly_female': { label: '👵 Elderly Women', icon: '👵' },
    'elderly_male': { label: '👴 Elderly Men', icon: '👴' },
    'teenage_female': { label: '👧 Teenage Girls', icon: '👧' },
    'teenage_male': { label: '👦 Teenage Boys', icon: '👦' },
    'celebrity': { label: '⭐ Celebrities', icon: '⭐' }
  };

  const ageGroups = [
    { value: 'all', label: 'All Ages' },
    { value: 'child', label: '🧒 Children' },
    { value: 'teen', label: '🧑 Teens' },
    { value: 'adult', label: '👤 Adults' },
    { value: 'elderly', label: '👴 Elderly' }
  ];

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

  useEffect(() => {
    fetchDocuments();
    fetchVoices();
    fetchJobs();
  }, []);

  useEffect(() => {
    if (documents.length > 0 || audioUrl || manualText) {
      setShowHelper(false);
    }
  }, [documents, audioUrl, manualText]);

  const fetchDocuments = async () => {
    try {
      const response = await api.get('/tts/documents');
      setDocuments(response.data.documents || []);
    } catch (err) {
      console.error('Error fetching documents:', err);
    }
  };

  const fetchVoices = async () => {
    try {
      const response = await api.get('/tts/voices');
      setVoices(response.data.voices || []);
    } catch (err) {
      console.error('Error fetching voices:', err);
    }
  };

  const fetchJobs = async () => {
    try {
      const response = await api.get('/tts/jobs');
      setJobs(response.data.jobs || []);
    } catch (err) {
      console.error('Error fetching jobs:', err);
    }
  };

  const updateTextStats = (text) => {
    if (!text) {
      setTextStats({ words: 0, characters: 0, sentences: 0, paragraphs: 0 });
      return;
    }
    
    const words = text.split(/\s+/).filter(w => w).length;
    const characters = text.length;
    const sentences = text.split(/[.!?]+/).filter(s => s.trim()).length;
    const paragraphs = text.split('\n\n').filter(p => p.trim()).length;
    
    setTextStats({ words, characters, sentences, paragraphs });
  };

  const handleTextChange = (e) => {
    const text = e.target.value;
    setManualText(text);
    updateTextStats(text);
  };

  const handleRewriteText = async () => {
    if (!manualText.trim()) {
      setError('Please enter some text to rewrite');
      return;
    }

    setIsRewriting(true);
    setError('');

    try {
      const response = await api.post('/tts/rewrite-text', {
        text: manualText,
        language: selectedLanguage
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.data.success) {
        setRewrittenText(response.data.rewritten);
        setSuccess('✅ Text rewritten successfully!');
        updateTextStats(response.data.rewritten);
        setShowHelper(false);
      } else {
        setError(response.data.error || 'Rewriting failed');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Rewriting failed');
    } finally {
      setIsRewriting(false);
    }
  };

  const getFilteredVoices = () => {
    let filtered = voices;
    
    if (genderFilter !== 'all') {
      filtered = filtered.filter(v => v.gender === genderFilter);
    }
    
    if (ageFilter !== 'all') {
      filtered = filtered.filter(v => v.age_group === ageFilter);
    }
    
    return filtered;
  };

  const filteredVoices = getFilteredVoices();

  const handleDocumentUpload = async (e) => {
    e.preventDefault();
    if (!documentFile) {
      setError('Please select a document');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    const formData = new FormData();
    formData.append('file', documentFile);

    try {
      const response = await api.post('/tts/upload-document', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setSuccess(`✅ Document uploaded successfully! ${response.data.word_count || 0} words extracted.`);
        // The documents endpoint intentionally returns metadata only. Keep the
        // server-side document ID so synthesis can fetch the extracted text.
        setSelectedDocument(response.data.document_id);
        const extractedText = response.data.extracted_text || response.data.text || '';
        setManualText(extractedText);
        setRewrittenText('');
        updateTextStats(extractedText);
        await fetchDocuments();
        setDocumentFile(null);
        document.getElementById('documentInput').value = '';
        setShowHelper(false);
      } else {
        setError(response.data.error || 'Upload failed');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleSynthesize = async () => {
    let textToSynthesize = '';
    let documentId = selectedDocument || null;
    
    // Priority: Use rewritten text if available, otherwise manual text, otherwise document
    if (rewrittenText) {
      textToSynthesize = rewrittenText;
    } else if (manualText) {
      textToSynthesize = manualText;
    } else if (selectedDocument) {
      // Let the API load the full extracted text. The list only contains
      // document metadata, so it never exposes extracted_text to the client.
      documentId = selectedDocument;
    } else {
      setError('Please provide text (type, upload document, or select from library)');
      return;
    }

    if (!documentId && !textToSynthesize.trim()) {
      setError('No text to synthesize');
      return;
    }

    setSynthesizing(true);
    setError('');
    setAudioUrl(null);

    try {
      const response = await api.post('/tts/synthesize', {
        text: documentId ? '' : textToSynthesize,
        document_id: documentId,
        voice_id: selectedVoice || null,
        language: selectedLanguage,
        gender: selectedVoice ? null : (genderFilter !== 'all' ? genderFilter : 'female'),
        age_group: selectedVoice ? null : (ageFilter !== 'all' ? ageFilter : 'adult')
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.data.success) {
        setAudioUrl(response.data.audio_url);
        setSuccess(`✅ Audio generated successfully! Duration: ${Math.round(response.data.duration)}s, ${response.data.word_count || 0} words`);
        fetchJobs();
        setShowHelper(false);
      } else {
        setError(response.data.error || 'Synthesis failed');
      }
    } catch (err) {
      console.error('Synthesis error:', err);
      setError(err.response?.data?.error || 'Synthesis failed');
    } finally {
      setSynthesizing(false);
    }
  };

  const previewVoice = async (genderKey) => {
    if (genderKey === 'all') return;
    setPreviewingVoice(genderKey);
    try {
      const resp = await api.post('/tts/preview-voice', { language: selectedLanguage, gender: genderKey });
      if (resp.data.success) {
        if (previewAudioRef.current) previewAudioRef.current.pause();
        const audio = new Audio(`${API_URL}${resp.data.audio_url}`);
        previewAudioRef.current = audio;
        audio.onended = () => setPreviewingVoice(null);
        await audio.play();
        return;
      }
    } catch (err) {
      console.error('Voice preview failed:', err);
      setError('Could not preview that voice right now.');
    }
    setPreviewingVoice(null);
  };

  const startVoiceRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      voiceStreamRef.current = stream;
      voiceMediaRecorderRef.current = new MediaRecorder(stream);
      voiceChunksRef.current = [];
      setVoiceRecordingSeconds(0);
      voiceTimerRef.current = setInterval(() => setVoiceRecordingSeconds((s) => s + 1), 1000);

      voiceMediaRecorderRef.current.ondataavailable = (e) => voiceChunksRef.current.push(e.data);
      voiceMediaRecorderRef.current.onstop = () => {
        clearInterval(voiceTimerRef.current);
        const blob = new Blob(voiceChunksRef.current, { type: 'audio/wav' });
        const file = new File([blob], `voice_sample_${Date.now()}.wav`, { type: 'audio/wav' });
        setVoiceFile(file);
      };

      voiceMediaRecorderRef.current.start();
      setVoiceRecording(true);
    } catch (err) {
      console.error(err);
      setError('Microphone access denied. Please check browser permissions.');
    }
  };

  const stopVoiceRecording = () => {
    if (voiceMediaRecorderRef.current && voiceRecording) {
      voiceMediaRecorderRef.current.stop();
      voiceStreamRef.current?.getTracks().forEach((t) => t.stop());
      setVoiceRecording(false);
    }
  };

  const handleVoiceRegistration = async (e) => {
    e.preventDefault();
    if (!voiceFile) {
      setError('Please select an audio file');
      return;
    }
    if (!voiceName.trim()) {
      setError('Please enter a voice name');
      return;
    }

    setRegisteringVoice(true);
    setError('');
    setSuccess('');

    const formData = new FormData();
    formData.append('name', voiceName);
    formData.append('audio', voiceFile);
    formData.append('language', voiceLanguage);

    try {
      const response = await api.post('/tts/register-voice', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setSuccess(`✅ Voice "${voiceName}" registered successfully!`);
        fetchVoices();
        setVoiceName('');
        setVoiceFile(null);
        document.getElementById('voiceInput').value = '';
      } else {
        setError(response.data.error || 'Registration failed');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed');
    } finally {
      setRegisteringVoice(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const clearManualText = () => {
    setManualText('');
    setRewrittenText('');
    setTextStats({ words: 0, characters: 0, sentences: 0, paragraphs: 0 });
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-icon">🔊</span>
            <span className="logo-text">Text-to-Speech Studio</span>
          </div>
          <p className="tagline">Convert text to natural Kinyarwanda speech with AI voices</p>
        </div>
        <div className="header-right">
          <div className="user-info">
            <div className="user-avatar">
              {user?.full_name?.charAt(0) || user?.username?.charAt(0) || 'U'}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.full_name || user?.username}</span>
              <span className="user-role-badge secretary">
                📋 Secretary
              </span>
            </div>
            <button onClick={onBack} className="back-btn-header" title="Back to Dashboard">
              ← Back
            </button>
          </div>
        </div>
      </header>

      <div className="main-content">
        {/* Welcome Banner */}
        <div className="tts-welcome">
          <div className="tts-welcome-content">
            <div className="tts-welcome-icon">🔊</div>
            <div className="tts-welcome-text">
              <h2>Text-to-Speech Studio</h2>
              <p>Type text, upload documents, and generate natural Kinyarwanda speech</p>
            </div>
          </div>
          <div className="tts-quick-tips">
            <span className="tip">✏️ Type or upload</span>
            <span className="tip">🔄 Rewrite for clarity</span>
            <span className="tip">🎤 Choose a voice</span>
            <span className="tip">🔊 Generate speech</span>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{error}</span>
            <button className="error-close" onClick={() => setError('')}>✕</button>
          </div>
        )}
        
        {success && (
          <div className="success-message">
            <span className="success-icon">✅</span>
            <span className="success-text">{success}</span>
            <button className="success-close" onClick={() => setSuccess('')}>✕</button>
          </div>
        )}

        {/* Tabs */}
        <div className="tts-tabs">
          <button className={`tab ${activeTab === 'synthesize' ? 'active' : ''}`} onClick={() => setActiveTab('synthesize')}>
            <span className="tab-icon">📄</span>
            <span className="tab-text">Synthesize</span>
          </button>
          <button className={`tab ${activeTab === 'voices' ? 'active' : ''}`} onClick={() => setActiveTab('voices')}>
            <span className="tab-icon">🎙️</span>
            <span className="tab-text">Voices ({voices.length})</span>
          </button>
          <button className={`tab ${activeTab === 'jobs' ? 'active' : ''}`} onClick={() => setActiveTab('jobs')}>
            <span className="tab-icon">📋</span>
            <span className="tab-text">Jobs ({jobs.length})</span>
          </button>
        </div>

        {/* Synthesize Tab */}
        {activeTab === 'synthesize' && (
          <div className="tts-synthesize">
            {/* Upload Document */}
            <div className="card input-card">
              <div className="card-header">
                <h3>📄 Upload Document</h3>
                <p className="card-subtitle">Supported: PDF, DOCX, TXT, Images (JPG, PNG)</p>
              </div>
              <form onSubmit={handleDocumentUpload}>
                <div className="upload-area">
                  <input
                    id="documentInput"
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.jpg,.jpeg,.png"
                    onChange={(e) => setDocumentFile(e.target.files[0])}
                    disabled={uploading}
                    style={{ display: 'none' }}
                  />
                  <label htmlFor="documentInput" className="upload-label">
                    {documentFile ? documentFile.name : '📂 Choose Document'}
                  </label>
                  <button type="submit" className="btn-upload" disabled={uploading}>
                    {uploading ? '⏳ Uploading...' : '📤 Upload'}
                  </button>
                </div>
              </form>
            </div>

            {/* Manual Text Input */}
            <div className="card input-card">
              <div className="card-header">
                <h3>✏️ Type Your Text</h3>
                <p className="card-subtitle">Type or paste your text for speech synthesis</p>
              </div>
              <div className="text-input-area">
                <textarea
                  ref={textareaRef}
                  className="text-area"
                  value={manualText}
                  onChange={handleTextChange}
                  placeholder="Type or paste your Kinyarwanda text here..."
                  rows={6}
                />
                <div className="text-stats">
                  <span>📝 {textStats.words} words</span>
                  <span>📖 {textStats.characters} characters</span>
                  <span>💬 {textStats.sentences} sentences</span>
                  <span>📄 {textStats.paragraphs} paragraphs</span>
                </div>
                <div className="text-actions">
                  <button 
                    className="btn-rewrite" 
                    onClick={handleRewriteText} 
                    disabled={isRewriting || !manualText.trim()}
                  >
                    {isRewriting ? '⏳ Rewriting...' : '🔄 Rewrite Text'}
                  </button>
                  <button className="btn-clear" onClick={clearManualText}>
                    🗑️ Clear
                  </button>
                </div>
                {rewrittenText && (
                  <div className="rewritten-text">
                    <h4>✅ Rewritten Text</h4>
                    <div className="rewritten-content">{rewrittenText}</div>
                    <button 
                      className="btn-use-rewritten"
                      onClick={() => {
                        setManualText(rewrittenText);
                        setRewrittenText('');
                        updateTextStats(rewrittenText);
                      }}
                    >
                      Use Rewritten Text
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Synthesize Speech */}
            <div className="card input-card">
              <div className="card-header">
                <h3>🎤 Synthesize Speech</h3>
                <p className="card-subtitle">Select a voice and generate speech from your text</p>
              </div>
              
              <div className="form-group">
                <label>📄 Select Document (Optional)</label>
                <select 
                  value={selectedDocument || ''} 
                  onChange={(e) => setSelectedDocument(e.target.value ? Number(e.target.value) : null)}
                  className="form-select"
                >
                  <option value="">Select a document...</option>
                  {documents.map(doc => (
                    <option key={doc.id} value={doc.id}>
                      {doc.filename} ({doc.word_count || 0} words)
                    </option>
                  ))}
                </select>
                <small className="form-hint">Leave empty to use typed text above</small>
              </div>

              {/* Voice Selection with Filters */}
              <div className="form-group">
                <label>🎤 Select Voice <small className="form-hint" style={{ fontWeight: 400 }}>— click a persona to hear it</small></label>

                {/* Gender Filters */}
                <div className="voice-filters">
                  <button
                    className={`voice-filter-btn ${genderFilter === 'all' ? 'active' : ''}`}
                    onClick={() => setGenderFilter('all')}
                  >
                    All Voices
                  </button>
                  {Object.entries(voiceCategories).map(([key, value]) => (
                    <button
                      key={key}
                      className={`voice-filter-btn ${genderFilter === key ? 'active' : ''}`}
                      onClick={() => { setGenderFilter(key); previewVoice(key); }}
                      disabled={previewingVoice !== null}
                    >
                      {previewingVoice === key ? '🔊' : value.icon} {value.label}
                    </button>
                  ))}
                </div>

                {/* Age Filters */}
                <div className="voice-age-filters">
                  {ageGroups.map(age => (
                    <button 
                      key={age.value}
                      className={`voice-age-btn ${ageFilter === age.value ? 'active' : ''}`}
                      onClick={() => setAgeFilter(age.value)}
                    >
                      {age.label}
                    </button>
                  ))}
                </div>

                <select 
                  value={selectedVoice || ''} 
                  onChange={(e) => setSelectedVoice(parseInt(e.target.value))}
                  className="form-select"
                >
                  <option value="">Default Voice</option>
                  {filteredVoices.map(voice => {
                    const genderIcon = voice.gender === 'female' ? '👩' : 
                                      voice.gender === 'male' ? '👨' : 
                                      voice.gender === 'child' ? '🧒' :
                                      voice.gender === 'elderly_female' ? '👵' :
                                      voice.gender === 'elderly_male' ? '👴' :
                                      voice.gender === 'teenage_female' ? '👧' :
                                      voice.gender === 'teenage_male' ? '👦' : '🎤';
                    
                    return (
                      <option key={voice.id} value={voice.id}>
                        {genderIcon} {voice.name} ({voice.language === 'rw' ? '🇷🇼 Kinyarwanda' : '🇬🇧 English'})
                      </option>
                    );
                  })}
                </select>
              </div>

              <button className="btn-submit" onClick={handleSynthesize} disabled={synthesizing || (!manualText.trim() && !rewrittenText.trim() && !selectedDocument)}>
                {synthesizing ? '⏳ Synthesizing...' : '🔊 Generate Speech'}
              </button>

              {audioUrl && (
                <div className="audio-playback">
                  <h4>▶️ Generated Audio</h4>
                  <audio controls src={`${API_URL}${audioUrl}`} className="audio-player" />
                  <button className="btn-download" onClick={() => window.open(`${API_URL}${audioUrl}`)}>
                    💾 Download Audio
                  </button>
                </div>
              )}
            </div>

            {/* Documents List */}
            <div className="card input-card">
              <div className="card-header">
                <h3>📚 My Documents</h3>
                <p className="card-subtitle">All your uploaded documents for text-to-speech</p>
              </div>
              {documents.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📭</div>
                  <h3>No documents uploaded yet</h3>
                  <p>Upload a document to get started with text-to-speech</p>
                </div>
              ) : (
                <div className="document-list">
                  {documents.map(doc => (
                    <div key={doc.id} className="document-item">
                      <div className="doc-info">
                        <span className="doc-icon">
                          {doc.file_type === 'pdf' ? '📄' : 
                           doc.file_type === 'docx' ? '📝' : 
                           doc.file_type === 'txt' ? '📃' : '🖼️'}
                        </span>
                        <span className="doc-name">{doc.filename}</span>
                        <span className="doc-meta">
                          {doc.word_count || 0} words • {formatDate(doc.created_at)}
                        </span>
                        <span className={`doc-status ${doc.status}`}>
                          {doc.status === 'completed' ? '✅ Ready' : '⏳ Processing'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Voices Tab */}
        {activeTab === 'voices' && (
          <div className="tts-voices">
            <div className="card input-card">
              <div className="card-header">
                <h3>🎙️ Register Custom Voice</h3>
                <p className="card-subtitle">Upload a short audio sample (3-10 seconds) to clone your voice</p>
              </div>
              <form onSubmit={handleVoiceRegistration}>
                <div className="form-group">
                  <label>Voice Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={voiceName}
                    onChange={(e) => setVoiceName(e.target.value)}
                    placeholder="e.g., My Voice, John's Voice"
                    disabled={registeringVoice}
                  />
                </div>

                <div className="form-group">
                  <label>Language</label>
                  <select 
                    className="form-select"
                    value={voiceLanguage} 
                    onChange={(e) => setVoiceLanguage(e.target.value)}
                  >
                    <option value="rw">🇷🇼 Kinyarwanda</option>
                    <option value="en">🇬🇧 English</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Audio Sample <small className="form-hint" style={{ fontWeight: 400 }}>— 10-20 seconds recommended for best cloning quality</small></label>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                    <input
                      id="voiceInput"
                      type="file"
                      accept=".wav,.mp3,.m4a"
                      onChange={(e) => setVoiceFile(e.target.files[0])}
                      disabled={registeringVoice || voiceRecording}
                      style={{ display: 'none' }}
                    />
                    <label htmlFor="voiceInput" className="upload-label" style={{ flex: 1, minWidth: 180 }}>
                      {voiceFile ? voiceFile.name : '📂 Choose Audio File'}
                    </label>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>or</span>
                    <button
                      type="button"
                      className={voiceRecording ? 'btn-clear' : 'btn-upload'}
                      onClick={voiceRecording ? stopVoiceRecording : startVoiceRecording}
                      disabled={registeringVoice}
                    >
                      {voiceRecording ? `⏹️ Stop (${voiceRecordingSeconds}s)` : '🎙️ Record Live'}
                    </button>
                  </div>
                </div>

                <button type="submit" className="btn-submit" disabled={registeringVoice}>
                  {registeringVoice ? '⏳ Registering...' : '🎤 Register Voice'}
                </button>
              </form>
            </div>

            <div className="card input-card">
              <div className="card-header">
                <h3>🎵 My Voices</h3>
                <p className="card-subtitle">Available voices for text-to-speech synthesis</p>
              </div>
              {voices.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">🎙️</div>
                  <h3>No voices registered yet</h3>
                  <p>Register your first custom voice above</p>
                </div>
              ) : (
                <div className="voice-list">
                  {voices.map(voice => (
                    <div key={voice.id} className="voice-item">
                      <div className="voice-info">
                        <span className="voice-icon">🎙️</span>
                        <span className="voice-name">{voice.name}</span>
                        <span className="voice-meta">
                          {voice.language === 'rw' ? '🇷🇼 Kinyarwanda' : '🇬🇧 English'}
                        </span>
                        <span className={`voice-status ${voice.is_active ? 'active' : 'inactive'}`}>
                          {voice.is_active ? '✅ Active' : '❌ Inactive'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Jobs Tab */}
        {activeTab === 'jobs' && (
          <div className="tts-jobs">
            <div className="card input-card">
              <div className="card-header">
                <h3>📋 Synthesis History</h3>
                <p className="card-subtitle">All your text-to-speech synthesis jobs</p>
              </div>
              {jobs.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📭</div>
                  <h3>No synthesis jobs yet</h3>
                  <p>Generate your first audio to see it here</p>
                </div>
              ) : (
                <div className="job-list">
                  {jobs.map(job => (
                    <div key={job.id} className="job-item">
                      <div className="job-info">
                        <span className="job-status">
                          {job.status === 'completed' ? '✅' : '⏳'}
                        </span>
                        <span className="job-document">📄 {job.document_name || 'Unknown'}</span>
                        <span className="job-voice">🎤 {job.voice_name || 'Default Voice'}</span>
                        <span className="job-date">📅 {formatDate(job.created_at)}</span>
                      </div>
                      {job.output_path && (
                        <div className="job-audio">
                          <audio controls src={`${API_URL}/tts/audio/${job.output_path.split('/').pop()}`} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .tts-welcome {
          background: linear-gradient(135deg, #1e3a5f 0%, #1877f2 100%);
          border-radius: 16px;
          padding: 20px 30px;
          margin-bottom: 24px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: 20px;
          box-shadow: 0 8px 30px rgba(24, 119, 242, 0.25);
        }

        .tts-welcome-content {
          display: flex;
          align-items: center;
          gap: 15px;
        }

        .tts-welcome-icon {
          font-size: 42px;
          background: rgba(255,255,255,0.15);
          padding: 10px;
          border-radius: 50%;
        }

        .tts-welcome-text h2 {
          color: white;
          font-size: 20px;
          font-weight: 700;
          margin: 0;
        }

        .tts-welcome-text p {
          color: rgba(255,255,255,0.85);
          margin: 4px 0 0;
          font-size: 14px;
        }

        .tts-quick-tips {
          display: flex;
          gap: 16px;
          flex-wrap: wrap;
        }

        .tts-quick-tips .tip {
          color: white;
          font-size: 13px;
          font-weight: 500;
          background: rgba(255,255,255,0.12);
          padding: 6px 14px;
          border-radius: 20px;
          border: 1px solid rgba(255,255,255,0.15);
        }

        .back-btn-header {
          background: rgba(255,255,255,0.15);
          border: none;
          color: white;
          padding: 8px 16px;
          border-radius: 40px;
          cursor: pointer;
          font-size: 13px;
          transition: all 0.2s;
          margin-left: 12px;
        }

        .back-btn-header:hover {
          background: rgba(255,255,255,0.25);
          transform: translateX(-4px);
        }

        .tts-tabs {
          display: flex;
          gap: 8px;
          padding: 0 0 20px 0;
          border-bottom: 2px solid #e2e8f0;
          margin-bottom: 24px;
        }

        .tts-tabs .tab {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          background: transparent;
          border: none;
          border-radius: 12px;
          cursor: pointer;
          font-weight: 600;
          font-size: 14px;
          transition: all 0.2s;
          color: #64748b;
          border-bottom: 3px solid transparent;
        }

        .tts-tabs .tab:hover {
          background: #f1f5f9;
          color: #1e293b;
        }

        .tts-tabs .tab.active {
          color: #1877f2;
          border-bottom-color: #1877f2;
          background: #eff6ff;
        }

        .tts-tabs .tab-icon {
          font-size: 18px;
        }

        .upload-area {
          display: flex;
          gap: 16px;
          align-items: center;
          flex-wrap: wrap;
        }

        .upload-label {
          flex: 1;
          padding: 14px 20px;
          background: #f8fafc;
          border: 2px dashed #e2e8f0;
          border-radius: 12px;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s;
          color: #64748b;
          font-weight: 500;
        }

        .upload-label:hover {
          background: #f1f5f9;
          border-color: #94a3b8;
        }

        .btn-upload,
        .btn-download {
          padding: 12px 28px;
          background: linear-gradient(135deg, #1877f2 0%, #0e5bc4 100%);
          color: white;
          border: none;
          border-radius: 40px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 14px;
        }

        .btn-upload:hover,
        .btn-download:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 15px rgba(24, 119, 242, 0.3);
        }

        .btn-upload:disabled {
          opacity: 0.5;
          cursor: not-allowed;
          transform: none;
        }

        .btn-download {
          background: #10b981;
          margin-top: 12px;
        }

        .btn-download:hover {
          background: #059669;
        }

        .form-group {
          margin-bottom: 16px;
        }

        .form-group label {
          display: block;
          font-weight: 600;
          font-size: 14px;
          color: #1e293b;
          margin-bottom: 6px;
        }

        .form-select,
        .form-input {
          width: 100%;
          padding: 12px 14px;
          border: 1px solid #e2e8f0;
          border-radius: 10px;
          font-size: 14px;
          transition: all 0.2s;
          background: white;
        }

        .form-select:focus,
        .form-input:focus {
          outline: none;
          border-color: #1877f2;
          box-shadow: 0 0 0 3px rgba(24, 119, 242, 0.1);
        }

        .form-hint {
          display: block;
          font-size: 11px;
          color: #94a3b8;
          margin-top: 4px;
        }

        .voice-filters {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-bottom: 8px;
        }

        .voice-filter-btn {
          padding: 6px 14px;
          background: #f1f5f9;
          border: 1px solid #e2e8f0;
          border-radius: 20px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 500;
          transition: all 0.2s;
          color: #64748b;
        }

        .voice-filter-btn:hover {
          background: #e2e8f0;
        }

        .voice-filter-btn.active {
          background: #1877f2;
          color: white;
          border-color: #1877f2;
        }

        .voice-age-filters {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-bottom: 8px;
        }

        .voice-age-btn {
          padding: 4px 12px;
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 16px;
          cursor: pointer;
          font-size: 11px;
          font-weight: 500;
          transition: all 0.2s;
          color: #64748b;
        }

        .voice-age-btn:hover {
          background: #e2e8f0;
        }

        .voice-age-btn.active {
          background: #8b5cf6;
          color: white;
          border-color: #8b5cf6;
        }

        .text-input-area {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .text-area {
          width: 100%;
          padding: 14px;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          font-size: 14px;
          font-family: inherit;
          line-height: 1.6;
          resize: vertical;
          min-height: 150px;
          transition: all 0.2s;
        }

        .text-area:focus {
          outline: none;
          border-color: #1877f2;
          box-shadow: 0 0 0 3px rgba(24, 119, 242, 0.1);
        }

        .text-stats {
          display: flex;
          gap: 16px;
          font-size: 12px;
          color: #64748b;
          padding: 8px 12px;
          background: #f8fafc;
          border-radius: 8px;
        }

        .text-actions {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
        }

        .btn-rewrite {
          padding: 10px 24px;
          background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
          color: white;
          border: none;
          border-radius: 40px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 14px;
        }

        .btn-rewrite:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);
        }

        .btn-rewrite:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-clear {
          padding: 10px 24px;
          background: #ef4444;
          color: white;
          border: none;
          border-radius: 40px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 14px;
        }

        .btn-clear:hover {
          background: #dc2626;
          transform: translateY(-2px);
        }

        .rewritten-text {
          margin-top: 12px;
          padding: 16px;
          background: #f0fdf4;
          border-radius: 12px;
          border: 1px solid #bbf7d0;
        }

        .rewritten-text h4 {
          margin: 0 0 8px;
          font-size: 14px;
          color: #166534;
        }

        .rewritten-content {
          font-size: 14px;
          line-height: 1.6;
          color: #1e293b;
          padding: 12px;
          background: white;
          border-radius: 8px;
          max-height: 200px;
          overflow-y: auto;
        }

        .btn-use-rewritten {
          margin-top: 10px;
          padding: 8px 20px;
          background: #10b981;
          color: white;
          border: none;
          border-radius: 30px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          font-size: 13px;
        }

        .btn-use-rewritten:hover {
          background: #059669;
          transform: translateY(-2px);
        }

        .audio-playback {
          margin-top: 16px;
          padding: 16px;
          background: #f8fafc;
          border-radius: 12px;
        }

        .audio-playback h4 {
          margin: 0 0 12px;
          font-size: 14px;
          color: #1e293b;
        }

        .audio-playback .audio-player {
          width: 100%;
        }

        .document-list,
        .voice-list,
        .job-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .document-item,
        .voice-item,
        .job-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 18px;
          background: #f8fafc;
          border-radius: 12px;
          flex-wrap: wrap;
          gap: 8px;
          border: 1px solid #eef2f6;
        }

        .doc-info,
        .voice-info,
        .job-info {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .doc-icon,
        .voice-icon {
          font-size: 24px;
        }

        .doc-name,
        .voice-name {
          font-weight: 500;
          color: #1e293b;
        }

        .doc-meta,
        .voice-meta {
          font-size: 12px;
          color: #64748b;
        }

        .doc-status,
        .voice-status {
          font-size: 12px;
          font-weight: 600;
        }

        .doc-status.completed {
          color: #10b981;
        }

        .doc-status.pending {
          color: #f59e0b;
        }

        .voice-status.active {
          color: #10b981;
        }

        .voice-status.inactive {
          color: #ef4444;
        }

        .job-audio {
          width: 100%;
          margin-top: 8px;
        }

        .job-audio audio {
          width: 100%;
        }

        .job-status {
          font-size: 18px;
        }

        .job-document,
        .job-voice,
        .job-date {
          font-size: 13px;
          color: #475569;
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
        }

        .empty-icon {
          font-size: 48px;
          margin-bottom: 12px;
          opacity: 0.5;
        }

        .empty-state h3 {
          font-size: 18px;
          color: #1e293b;
          margin: 0 0 8px;
        }

        .empty-state p {
          color: #64748b;
          font-size: 14px;
          margin: 0;
        }

        .card-header {
          margin-bottom: 16px;
        }

        .card-header h3 {
          margin: 0;
          font-size: 18px;
          color: #1e293b;
        }

        .card-subtitle {
          color: #64748b;
          font-size: 13px;
          margin: 4px 0 0;
        }

        @media (max-width: 768px) {
          .tts-welcome {
            flex-direction: column;
            text-align: center;
          }

          .tts-welcome-content {
            flex-direction: column;
          }

          .tts-quick-tips {
            justify-content: center;
          }

          .tts-tabs {
            flex-direction: column;
            border-bottom: none;
          }

          .tts-tabs .tab {
            border-bottom: 2px solid transparent;
            justify-content: center;
          }

          .upload-area {
            flex-direction: column;
          }

          .upload-label {
            width: 100%;
          }

          .btn-upload {
            width: 100%;
            justify-content: center;
          }

          .document-item,
          .voice-item,
          .job-item {
            flex-direction: column;
            align-items: flex-start;
          }

          .doc-info,
          .voice-info,
          .job-info {
            width: 100%;
          }

          .back-btn-header {
            margin-left: 0;
            margin-top: 8px;
          }

          .voice-filters {
            justify-content: center;
          }

          .voice-age-filters {
            justify-content: center;
          }

          .text-stats {
            flex-wrap: wrap;
          }

          .text-actions {
            flex-direction: column;
          }

          .btn-rewrite,
          .btn-clear {
            width: 100%;
            justify-content: center;
          }
        }

        @media (max-width: 480px) {
          .tts-welcome-icon {
            font-size: 32px;
          }

          .tts-welcome-text h2 {
            font-size: 17px;
          }

          .tts-quick-tips .tip {
            font-size: 11px;
            padding: 4px 10px;
          }
        }
      `}</style>
    </div>
  );
}

export default TTSDashboard;
