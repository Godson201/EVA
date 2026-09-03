import React, { useState } from 'react';
import axios from 'axios';
import { THEMES, FONTS, MODES } from './themeConfig';

const API_URL = 'http://localhost:8000';

function SettingsPage({ user, settings, onUpdate }) {
  const [themeColor, setThemeColor] = useState((settings && settings.theme_color) || 'indigo');
  const [fontStyle, setFontStyle] = useState((settings && settings.font_style) || 'inter');
  const [defaultMode, setDefaultMode] = useState((settings && settings.default_mode) || 'both');
  const [avatarFile, setAvatarFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);

  const avatarUrl = (settings && settings.avatar_url) || (user && user.avatar_url);

  const api = axios.create({ baseURL: API_URL });
  api.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
  });

  const saveAppearance = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.put('/api/user/settings', {
        theme_color: themeColor,
        font_style: fontStyle,
        default_mode: defaultMode,
      });
      if (onUpdate) onUpdate({ theme_color: themeColor, font_style: fontStyle, default_mode: defaultMode });
      setMsg('Settings saved');
    } catch (err) {
      console.error(err);
      setMsg('Could not save settings — please try again');
    } finally {
      setSaving(false);
    }
  };

  const uploadAvatar = async (e) => {
    e.preventDefault();
    if (!avatarFile) {
      setMsg('Choose an image first');
      return;
    }
    setUploading(true);
    setMsg(null);
    const fd = new FormData();
    fd.append('file', avatarFile);
    try {
      const resp = await api.post('/api/user/profile/avatar', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (onUpdate) onUpdate({ avatar_url: resp.data.avatar_url });
      setMsg('Profile picture updated');
      setAvatarFile(null);
    } catch (err) {
      console.error(err);
      setMsg('Upload failed — please try a different image');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="dash-hero" style={{ textAlign: 'left', padding: '4px 0 6px' }}>
        <h1 style={{ fontSize: 22 }}>Settings</h1>
        <p>Personalize how AudioText Pro looks and behaves for you</p>
      </div>

      {msg && <div className="dash-alert">{msg}</div>}

      <div className="dash-row">
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Profile Picture</h3>
              <p>Shown in the sidebar and across the app</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {avatarUrl ? (
              <img
                src={avatarUrl.startsWith('http') ? avatarUrl : `${API_URL}${avatarUrl}`}
                alt="avatar"
                style={{ width: 64, height: 64, borderRadius: '50%', objectFit: 'cover', border: '1px solid var(--d-border)' }}
              />
            ) : (
              <div style={{
                width: 64, height: 64, borderRadius: '50%', background: 'var(--d-primary)', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 20,
              }}>
                {((user && (user.full_name || user.username)) || 'U').charAt(0).toUpperCase()}
              </div>
            )}
            <form onSubmit={uploadAvatar} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input type="file" accept="image/*" onChange={(e) => setAvatarFile(e.target.files[0])} />
              <button className="dash-btn dash-btn-sm dash-btn-primary" type="submit" disabled={uploading}>
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
            </form>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Default Mode</h3>
              <p>Which workspace opens first</p>
            </div>
          </div>
          <div className="dash-choice-group">
            {Object.entries(MODES).map(([key, m]) => (
              <button
                key={key}
                type="button"
                className={`dash-choice ${defaultMode === key ? 'active' : ''}`}
                onClick={() => setDefaultMode(key)}
              >
                <div>
                  <div className="dash-choice-title">{m.label}</div>
                  <div className="dash-choice-sub">{m.sub}</div>
                </div>
                <span className="dash-choice-check" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="dash-row">
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Theme Color</h3>
              <p>Pick an accent color for your dashboard</p>
            </div>
          </div>
          <div className="dash-swatches">
            {Object.entries(THEMES).map(([key, t]) => (
              <button
                key={key}
                type="button"
                title={t.label}
                className={`dash-swatch ${themeColor === key ? 'active' : ''}`}
                style={{ background: t.primary }}
                onClick={() => setThemeColor(key)}
              />
            ))}
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Font Style</h3>
              <p>Choose how text renders across the app</p>
            </div>
          </div>
          <div className="dash-choice-group">
            {Object.entries(FONTS).map(([key, f]) => (
              <button
                key={key}
                type="button"
                className={`dash-choice ${fontStyle === key ? 'active' : ''}`}
                style={{ fontFamily: f.family }}
                onClick={() => setFontStyle(key)}
              >
                <div className="dash-choice-title">{f.label}</div>
                <span className="dash-choice-check" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="dash-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>AudioText Pro v9.0</div>
          <div style={{ fontSize: 12, color: 'var(--d-text-muted)' }}>This app updates automatically — you're always on the latest version.</div>
        </div>
        <button className="dash-btn dash-btn-primary" onClick={saveAppearance} disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

export default SettingsPage;
