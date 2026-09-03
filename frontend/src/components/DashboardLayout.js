import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';
import SettingsPage from './SettingsPage';
import HelpSupportPage from './HelpSupportPage';
import HistoryPage from './HistoryPage';
import { themeVars, fontFamily } from './themeConfig';

const API_URL = 'http://localhost:8000';

const FolderIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>
);
const ClockIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>
);
const GearIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.96 19a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87A1.7 1.7 0 0 0 3.04 13H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.65 7.96a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.51V2a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.51 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9c.14.6.51 1.12 1.51 1.09H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1.91Z"/></svg>
);
const HelpIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2-2.4 3.7"/><path d="M12 17.5h.01"/></svg>
);
const BellIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
);
const CloseIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
);
const LogoutIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>
);

function DashboardLayout({ user, children, onClose, onLogout, hasNotifications = false }) {
  const [page, setPage] = useState('empty');
  const [settings, setSettings] = useState(null);

  const displayName = (user && (user.full_name || user.username)) || 'User';
  const initials = displayName
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(p => p[0].toUpperCase())
    .join('') || 'U';

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) return;
    axios.get(`${API_URL}/api/user/settings`, { headers: { Authorization: `Bearer ${token}` } })
      .then(resp => setSettings(resp.data.settings || {}))
      .catch(() => {});
  }, []);

  const updateSettings = (patch) => setSettings(prev => ({ ...(prev || {}), ...patch }));

  const avatarUrl = (settings && settings.avatar_url) || (user && user.avatar_url);
  const shellStyle = {
    ...themeVars((settings && settings.theme_color) || 'indigo'),
    fontFamily: fontFamily((settings && settings.font_style) || 'inter'),
  };

  return (
    <div className="dash-shell" style={shellStyle}>
      <aside className="dash-sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo"><span /><span /><span /><span /></div>
          <div className="sidebar-brand-text">
            <strong>EVA</strong>
            <span>Dashboard</span>
          </div>
        </div>

        <nav className="dash-nav">
          <button className={`nav-btn ${page === 'dashboard' ? 'active' : ''}`} onClick={() => setPage('dashboard')}>
            <FolderIcon /><span className="nav-label">Workspace</span>
          </button>
          <button className={`nav-btn ${page === 'history' ? 'active' : ''}`} onClick={() => setPage('history')}>
            <ClockIcon /><span className="nav-label">Historical Activity</span>
          </button>
        </nav>

        <div className="sidebar-spacer" />

        <nav className="dash-nav">
          <button className={`nav-btn ${page === 'settings' ? 'active' : ''}`} onClick={() => setPage('settings')}>
            <GearIcon /><span className="nav-label">Settings</span>
          </button>
          <button className={`nav-btn ${page === 'help' ? 'active' : ''}`} onClick={() => setPage('help')}>
            <HelpIcon /><span className="nav-label">Help &amp; Support</span>
          </button>
        </nav>

        <div className="sidebar-profile">
          {avatarUrl ? (
            <img src={avatarUrl.startsWith('http') ? avatarUrl : `${API_URL}${avatarUrl}`} alt="avatar" className="sidebar-avatar" />
          ) : (
            <div className="sidebar-avatar">{initials}</div>
          )}
          <div className="sidebar-profile-text">
            <strong>{displayName}</strong>
            <span>{(user && user.email) || ''}</span>
          </div>
        </div>
      </aside>

      <main className="dash-main">
        <header className="dash-header">
          <div className="header-actions">
            <button className="dash-btn dash-btn-icon dash-bell" title="Notifications">
              <BellIcon />
              {hasNotifications && <span className="dash-bell-dot" />}
            </button>
            <button className="dash-btn dash-btn-icon" onClick={onClose} title="Close Dashboard"><CloseIcon /></button>
            <button
              className="dash-btn dash-btn-icon"
              title="Sign Out"
              onClick={() => {
                if (onLogout) {
                  if (window.confirm('Sign out from your session?')) onLogout();
                } else if (window.confirm('Sign out?')) {
                  window.location.reload();
                }
              }}
            >
              <LogoutIcon />
            </button>
          </div>
        </header>

        <section className="dash-content">
          {page === 'empty' && (
            <div className="dash-page-placeholder">
              <h2>Welcome, {displayName}</h2>
              <p>Select <strong>Workspace</strong> or <strong>Historical Activity</strong> from the sidebar to get started.</p>
            </div>
          )}
          {page === 'dashboard' && children}
          {page === 'history' && <HistoryPage user={user} />}
          {page === 'settings' && <SettingsPage user={user} settings={settings} onUpdate={updateSettings} />}
          {page === 'help' && <HelpSupportPage user={user} />}
        </section>
      </main>
    </div>
  );
}

export default DashboardLayout;
