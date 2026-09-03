import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = 'http://localhost:8000';

const MicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 19v3"/></svg>
);
const TrashIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>
);
const DownloadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></svg>
);
const UserIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
);
const ImageIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>
);
const GlobeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20Z"/></svg>
);
const GearIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87 2 2 0 1 1-2.83 2.83 1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.96 19a1.7 1.7 0 0 0-1.87.34 2 2 0 1 1-2.83-2.83 1.7 1.7 0 0 0 .34-1.87A1.7 1.7 0 0 0 3.04 13H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.65 7.96a1.7 1.7 0 0 0-.34-1.87 2 2 0 1 1 2.83-2.83 1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.51V2a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.51 1.7 1.7 0 0 0 1.87-.34 2 2 0 1 1 2.83 2.83 1.7 1.7 0 0 0-.34 1.87V9c.14.6.51 1.12 1.51 1.09H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1.91Z"/></svg>
);
const MailIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/></svg>
);
const LogInIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="M10 17l5-5-5-5M15 12H3"/></svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
);
const ActivityIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
);

const ACTION_META = {
  LOGIN: { icon: <LogInIcon />, label: 'Signed in' },
  TRANSCRIBE: { icon: <MicIcon />, label: 'Transcribed audio' },
  SAVE_SPEECH: { icon: <MicIcon />, label: 'Saved a recording' },
  SAVE_KINYARWANDA: { icon: <MicIcon />, label: 'Saved a Kinyarwanda recording' },
  DELETE_RECORD: { icon: <TrashIcon />, label: 'Deleted a record' },
  DELETE_SPEECH: { icon: <TrashIcon />, label: 'Deleted a recording' },
  EXPORT_PDF: { icon: <DownloadIcon />, label: 'Exported a PDF' },
  UPDATE_PROFILE: { icon: <UserIcon />, label: 'Updated profile' },
  UPLOAD_AVATAR: { icon: <ImageIcon />, label: 'Updated profile picture' },
  SET_LANGUAGE: { icon: <GlobeIcon />, label: 'Changed language' },
  UPDATE_SETTINGS: { icon: <GearIcon />, label: 'Updated settings' },
  CONTACT_SUPPORT: { icon: <MailIcon />, label: 'Contacted support' },
  CREATE_USER: { icon: <UsersIcon />, label: 'Created a user' },
  UPDATE_USER_STATUS: { icon: <UsersIcon />, label: 'Changed a user’s status' },
  CHANGE_ROLE: { icon: <UsersIcon />, label: 'Changed a user’s role' },
  DELETE_USER: { icon: <UsersIcon />, label: 'Deleted a user' },
};

const humanize = (action) => (action || '')
  .toLowerCase()
  .split('_')
  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
  .join(' ');

function HistoryPage({ user }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('token');
    axios.get(`${API_URL}/api/user/activity`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(resp => setLogs(resp.data.logs || []))
      .catch(err => {
        console.error(err);
        setError('Unable to load your activity history');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="dash-hero" style={{ textAlign: 'left', padding: '4px 0 6px' }}>
        <h1 style={{ fontSize: 22 }}>Historical Activity</h1>
        <p>A timeline of {(user && (user.full_name || user.username)) || 'your'} account activity</p>
      </div>

      <div className="dash-card">
        {loading ? (
          <div className="dash-empty">Loading...</div>
        ) : error ? (
          <div className="dash-empty">{error}</div>
        ) : logs.length === 0 ? (
          <div className="dash-empty">No activity recorded yet</div>
        ) : (
          <div>
            {logs.map(log => {
              const meta = ACTION_META[log.action] || { icon: <ActivityIcon />, label: humanize(log.action) };
              return (
                <div key={log.id} className="dash-guide-item">
                  <div className="dash-guide-icon">{meta.icon}</div>
                  <div className="dash-guide-item-body">
                    <div className="dash-guide-title">{meta.label}</div>
                    {log.details && <div className="dash-guide-sub">{log.details}</div>}
                  </div>
                  <span className="dash-guide-time">{new Date(log.created_at).toLocaleString()}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default HistoryPage;
