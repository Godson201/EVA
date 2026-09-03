import React, { useState } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';
const SUPPORT_EMAIL = 'happyprincegodson@gmail.com';
const SUPPORT_WHATSAPP_DISPLAY = '+250 783 688 266';
const SUPPORT_WHATSAPP_DIGITS = '250783688266';

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 19v3"/></svg>
);
const GlobeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20Z"/></svg>
);
const SpeakerIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m11 5-6 4H2v6h3l6 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/></svg>
);
const SaveIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8M7 3v5h8"/></svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
);
const MailIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/></svg>
);
const WhatsAppIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.7-.9-2-1-.3-.1-.5-.1-.7.1-.2.3-.8 1-.9 1.2-.2.2-.3.2-.6.1-.3-.1-1.3-.5-2.4-1.5-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.1.3-.3.4-.5.1-.1.2-.3.3-.4.1-.2 0-.4 0-.5C10 9 9.4 7.6 9.1 7c-.2-.5-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.4s1 2.8 1.2 3c.1.2 2.1 3.2 5 4.5.7.3 1.3.5 1.7.6.7.2 1.4.2 1.9.1.6-.1 1.7-.7 1.9-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3ZM12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Z"/></svg>
);

const GUIDE_ITEMS = [
  {
    icon: <MicIcon />,
    title: 'Record or upload audio',
    sub: 'From the main workspace, record live or upload an audio file (MP3, WAV, M4A) to get an instant transcription.',
  },
  {
    icon: <GlobeIcon />,
    title: 'Choose your language',
    sub: 'AudioText Pro supports English and Kinyarwanda speech recognition — pick a language before transcribing.',
  },
  {
    icon: <SpeakerIcon />,
    title: 'Text-to-Speech Studio',
    sub: 'Open the TTS Studio to type or upload text, rewrite it for clarity, and generate natural speech in a voice of your choice.',
  },
  {
    icon: <SaveIcon />,
    title: 'Save, play & export',
    sub: 'Every transcription is saved to your workspace. Play the original audio, download a summary, or export to TXT/PDF.',
  },
  {
    icon: <UsersIcon />,
    title: 'Dashboards by role',
    sub: 'Your dashboard adapts to your role: personal records for Users, workspace oversight for Managers, and full user/activity management for Directors.',
  },
];

function HelpSupportPage({ user }) {
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);

  const api = axios.create({ baseURL: API_URL });
  api.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
  });

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!message.trim()) {
      setStatus({ type: 'error', text: 'Please write a message first' });
      return;
    }
    setSending(true);
    setStatus(null);
    try {
      await api.post('/api/support/contact', { message });
      setStatus({ type: 'success', text: "Message sent — our support team will reply to your email." });
      setMessage('');
    } catch (err) {
      console.error(err);
      setStatus({ type: 'error', text: err.response?.data?.detail || 'Could not send your message. Try email or WhatsApp instead.' });
    } finally {
      setSending(false);
    }
  };

  const mailtoHref = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('AudioText Pro Support')}`;
  const whatsappHref = `https://wa.me/${SUPPORT_WHATSAPP_DIGITS}`;

  return (
    <div>
      <div className="dash-hero" style={{ textAlign: 'left', padding: '4px 0 6px' }}>
        <h1 style={{ fontSize: 22 }}>Help &amp; Support</h1>
        <p>Learn how AudioText Pro works, or reach out directly</p>
      </div>

      <div className="dash-card">
        <div className="dash-card-header"><div><h3>How the system works</h3></div></div>
        <div>
          {GUIDE_ITEMS.map((g, i) => (
            <div key={i} className="dash-guide-item">
              <div className="dash-guide-icon">{g.icon}</div>
              <div>
                <div className="dash-guide-title">{g.title}</div>
                <div className="dash-guide-sub">{g.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="dash-row">
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Message Support</h3>
              <p>Sends straight to our support officer's inbox</p>
            </div>
          </div>
          {status && <div className={`dash-alert ${status.type === 'error' ? 'dash-alert-error' : ''}`}>{status.text}</div>}
          <form onSubmit={sendMessage}>
            <div className="dash-field">
              <label>Your message</label>
              <textarea
                placeholder="Describe the issue or question you have..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </div>
            <button className="dash-btn dash-btn-primary" type="submit" disabled={sending}>
              {sending ? 'Sending...' : 'Send Message'}
            </button>
          </form>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Direct Contact</h3>
              <p>Reach the support officer directly</p>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <a className="dash-btn" href={mailtoHref}><MailIcon /> {SUPPORT_EMAIL}</a>
            <a className="dash-btn" href={whatsappHref} target="_blank" rel="noreferrer"><WhatsAppIcon /> {SUPPORT_WHATSAPP_DISPLAY}</a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HelpSupportPage;
