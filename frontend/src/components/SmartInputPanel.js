import React, { useState, useRef } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 19v3"/></svg>
);
const StopIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
);
const AudioFileIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
);
const DocIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
);
const ImageIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>
);
const TranslateIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1"/><path d="m22 22-5-10-5 10M14 18h6"/></svg>
);
const CopyIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
);

const LANG_LABEL = { en: 'English', rw: 'Kinyarwanda' };

function SmartInputPanel() {
  const [language, setLanguage] = useState('rw');
  const [text, setText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [busy, setBusy] = useState(null); // 'recording' | 'transcribing' | 'document' | 'image' | 'translating' | null
  const [status, setStatus] = useState(null); // { type, text }
  const [translatedText, setTranslatedText] = useState('');
  const [translatedLang, setTranslatedLang] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const audioFileInputRef = useRef(null);
  const documentInputRef = useRef(null);
  const imageInputRef = useRef(null);

  const api = axios.create({ baseURL: API_URL });
  api.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
  });

  const clearStatusSoon = () => setTimeout(() => setStatus(null), 5000);

  const uploadAudioBlob = async (file) => {
    setBusy('transcribing');
    setStatus(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('language', language);
    try {
      const resp = await api.post('/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (resp.data.success) {
        setText(resp.data.text || '');
        setTranslatedText('');
        setStatus({ type: 'success', text: 'Transcribed and saved to My Transcriptions.' });
      } else {
        setStatus({ type: 'error', text: resp.data.error || 'Could not transcribe that audio.' });
      }
    } catch (err) {
      console.error(err);
      setStatus({ type: 'error', text: err.response?.data?.error || 'Transcription failed. Please try again.' });
    } finally {
      setBusy(null);
      clearStatusSoon();
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);

      mediaRecorderRef.current.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      mediaRecorderRef.current.onstop = () => {
        clearInterval(timerRef.current);
        setRecordingSeconds(0);
        const blob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const file = new File([blob], 'recording.wav', { type: 'audio/wav' });
        uploadAudioBlob(file);
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setBusy('recording');
    } catch (err) {
      console.error(err);
      setStatus({ type: 'error', text: 'Microphone access denied. Please check browser permissions.' });
      clearStatusSoon();
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setIsRecording(false);
    }
  };

  const handleAudioFile = (e) => {
    const file = e.target.files[0];
    if (file) uploadAudioBlob(file);
    e.target.value = '';
  };

  const handleDocOrImage = async (e, kind) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    setBusy(kind);
    setStatus(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const resp = await api.post('/tts/upload-document', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (resp.data.success) {
        setText(resp.data.extracted_text || '');
        setTranslatedText('');
        setStatus({ type: 'success', text: kind === 'image' ? 'Text extracted from image.' : 'Text extracted from document.' });
      } else {
        setStatus({ type: 'error', text: resp.data.error || 'Could not extract text from that file.' });
      }
    } catch (err) {
      console.error(err);
      setStatus({ type: 'error', text: err.response?.data?.detail || 'Upload failed. Please try again.' });
    } finally {
      setBusy(null);
      clearStatusSoon();
    }
  };

  const translate = async () => {
    if (!text.trim()) return;
    const targetLang = language === 'rw' ? 'en' : 'rw';
    setBusy('translating');
    setStatus(null);
    try {
      const resp = await api.post('/api/translate', { text, source_lang: language, target_lang: targetLang });
      if (resp.data.success) {
        setTranslatedText(resp.data.translated_text || '');
        setTranslatedLang(targetLang);
      }
    } catch (err) {
      console.error(err);
      setStatus({ type: 'error', text: err.response?.data?.detail || 'Translation failed. Please try again.' });
      clearStatusSoon();
    } finally {
      setBusy(null);
    }
  };

  const copyTranslation = () => {
    if (translatedText) navigator.clipboard.writeText(translatedText);
  };

  const clearAll = () => {
    setText('');
    setTranslatedText('');
    setTranslatedLang(null);
    setStatus(null);
  };

  const targetLangLabel = LANG_LABEL[language === 'rw' ? 'en' : 'rw'];

  return (
    <div className="dash-hero-search" style={{ textAlign: 'left' }}>
      <div className="dash-choice-group" style={{ flexDirection: 'row', marginBottom: 12 }}>
        {['rw', 'en'].map((code) => (
          <button
            key={code}
            type="button"
            className={`dash-choice ${language === code ? 'active' : ''}`}
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={() => setLanguage(code)}
          >
            <span className="dash-choice-title">{LANG_LABEL[code]}</span>
          </button>
        ))}
      </div>

      <textarea
        placeholder="Type here, or record / upload audio, a document, or a picture..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        style={{
          width: '100%', minHeight: 110, border: '1px solid var(--d-border)', borderRadius: 12,
          padding: 12, fontSize: 14, fontFamily: 'inherit', resize: 'vertical', color: 'var(--d-text)',
        }}
      />

      {status && (
        <div className={`dash-alert ${status.type === 'error' ? 'dash-alert-error' : ''}`} style={{ marginTop: 10, marginBottom: 0 }}>
          {status.text}
        </div>
      )}

      <div className="dash-hero-search-row" style={{ borderTop: 'none', paddingTop: 10, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`dash-btn dash-btn-sm ${isRecording ? 'dash-btn-danger' : ''}`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={busy && busy !== 'recording'}
          >
            {isRecording ? <StopIcon /> : <MicIcon />}
            {isRecording ? `Stop (${recordingSeconds}s)` : 'Record'}
          </button>

          <button type="button" className="dash-btn dash-btn-sm" onClick={() => audioFileInputRef.current?.click()} disabled={!!busy}>
            <AudioFileIcon /> Audio File
          </button>
          <input ref={audioFileInputRef} type="file" accept="audio/*" style={{ display: 'none' }} onChange={handleAudioFile} />

          <button type="button" className="dash-btn dash-btn-sm" onClick={() => documentInputRef.current?.click()} disabled={!!busy}>
            <DocIcon /> Document
          </button>
          <input ref={documentInputRef} type="file" accept=".pdf,.docx,.doc,.txt" style={{ display: 'none' }} onChange={(e) => handleDocOrImage(e, 'document')} />

          <button type="button" className="dash-btn dash-btn-sm" onClick={() => imageInputRef.current?.click()} disabled={!!busy}>
            <ImageIcon /> Picture
          </button>
          <input ref={imageInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => handleDocOrImage(e, 'image')} />
        </div>

        {text.trim() && (
          <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
            <button type="button" className="dash-btn dash-btn-sm" onClick={clearAll} disabled={!!busy}>Clear</button>
            <button type="button" className="dash-btn dash-btn-sm dash-btn-primary" onClick={translate} disabled={!!busy}>
              <TranslateIcon /> {busy === 'translating' ? 'Translating...' : `Translate to ${targetLangLabel}`}
            </button>
          </div>
        )}
      </div>

      {busy && busy !== 'recording' && (
        <div className="dash-guide-sub" style={{ marginTop: 8 }}>
          {busy === 'transcribing' && 'Transcribing audio...'}
          {busy === 'document' && 'Extracting text from document...'}
          {busy === 'image' && 'Reading text from image...'}
          {busy === 'translating' && 'Translating...'}
        </div>
      )}

      {translatedText && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--d-border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className="dash-badge">{LANG_LABEL[translatedLang]}</span>
            <button type="button" className="dash-btn dash-btn-sm" onClick={copyTranslation}><CopyIcon /> Copy</button>
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--d-text)', whiteSpace: 'pre-wrap' }}>{translatedText}</div>
        </div>
      )}
    </div>
  );
}

export default SmartInputPanel;
