import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import DashboardLayout from './DashboardLayout';
import { BarChart, DonutChart } from './DashCharts';
import SmartInputPanel from './SmartInputPanel';

const API_URL = 'http://localhost:8000';

const ChatIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
);
const DocIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
);
const GlobeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20 15 15 0 0 1 0-20Z"/></svg>
);

function UserDashboard({ user, onClose, onLogout }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState({ full_name: '', department: '', phone: '' });
  const [language, setLanguage] = useState('en');
  const [avatarFile, setAvatarFile] = useState(null);
  const [msg, setMsg] = useState(null);

  const profileRef = useRef(null);
  const transcriptionsRef = useRef(null);

  const api = axios.create({ baseURL: API_URL });
  api.interceptors.request.use((cfg) => {
    const token = localStorage.getItem('token');
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
  });

  useEffect(() => {
    fetchRecords();
  }, []);

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/records');
      setRecords(resp.data.records || []);
    } catch (err) {
      console.error(err);
      setMsg('Unable to load records');
    } finally {
      setLoading(false);
    }
  };

  const deleteRecord = async (id) => {
    if (!window.confirm('Delete this record?')) return;
    try {
      await api.delete(`/record/${id}`);
      setMsg('Deleted');
      fetchRecords();
    } catch (err) {
      console.error(err);
      setMsg('Delete failed');
    }
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    try {
      await api.put('/api/user/profile', profile);
      setMsg('Profile updated');
    } catch (err) {
      console.error(err);
      setMsg('Update failed');
    }
  };

  const saveLanguage = async (e) => {
    e.preventDefault();
    try {
      const resp = await api.post('/api/user/language', { language });
      setMsg(`Language set to ${resp.data.language}`);
    } catch (err) {
      console.error(err);
      setMsg('Language update failed');
    }
  };

  const uploadAvatar = async (e) => {
    e.preventDefault();
    if (!avatarFile) return setMsg('Choose a file');
    const fd = new FormData();
    fd.append('file', avatarFile);
    try {
      await api.post('/api/user/profile/avatar', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMsg('Avatar uploaded');
    } catch (err) {
      console.error(err);
      setMsg('Upload failed');
    }
  };

  const scrollTo = (ref) => ref.current && ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const englishCount = records.filter(r => r.language_detected === 'en').length;
  const kinyarwandaCount = records.filter(r => r.language_detected === 'rw').length;

  // Last 7 days of real activity, derived from record timestamps.
  const last7Days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - (6 - i));
    return d;
  });
  const dayCounts = last7Days.map(day => {
    const next = new Date(day);
    next.setDate(next.getDate() + 1);
    return records.filter(r => {
      const rd = new Date(r.created_at);
      return rd >= day && rd < next;
    }).length;
  });
  const dayLabels = last7Days.map(d => d.toLocaleDateString(undefined, { weekday: 'short' }));
  const thisWeekCount = dayCounts.reduce((a, b) => a + b, 0);

  const recentInWeek = records
    .map(r => {
      const rd = new Date(r.created_at);
      rd.setHours(0, 0, 0, 0);
      const idx = last7Days.findIndex(d => d.getTime() === rd.getTime());
      return { ...r, dayIndex: idx };
    })
    .filter(r => r.dayIndex !== -1)
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5);

  const timelineColors = ['var(--d-blue)', 'var(--d-green)', 'var(--d-purple)', 'var(--d-orange)', 'var(--d-blue)'];

  return (
    <DashboardLayout user={user} onClose={onClose} onLogout={onLogout}>
      <div className="dash-hero">
        <h1>Welcome back, {(user && (user.full_name || user.username)) || 'there'}! 👋</h1>
        <p>Type, record, or upload audio, a document, or a picture — then translate it</p>
        <SmartInputPanel />
      </div>

      <div>
        <h2 className="dash-section-title">Quick Actions</h2>
        <div className="dash-quick-actions">
          <button className="dash-quick-tile" onClick={() => scrollTo(profileRef)}>
            <div className="dash-quick-icon blue"><ChatIcon /></div>
            <div className="dash-quick-title">My Profile</div>
            <div className="dash-quick-sub">Update your name, department and phone</div>
            <div className="dash-quick-arrow">→</div>
          </button>
          <button className="dash-quick-tile" onClick={() => scrollTo(transcriptionsRef)}>
            <div className="dash-quick-icon green"><DocIcon /></div>
            <div className="dash-quick-title">My Transcriptions</div>
            <div className="dash-quick-sub">Play, review or delete saved recordings</div>
            <div className="dash-quick-arrow">→</div>
          </button>
          <button className="dash-quick-tile" onClick={() => scrollTo(profileRef)}>
            <div className="dash-quick-icon purple"><GlobeIcon /></div>
            <div className="dash-quick-title">Language Settings</div>
            <div className="dash-quick-sub">Switch between English and Kinyarwanda</div>
            <div className="dash-quick-arrow">→</div>
          </button>
        </div>
      </div>

      <div className="dash-charts-row">
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Usage Overview</h3>
              <p>Last 7 days</p>
            </div>
          </div>
          <div className="dash-stat-value" style={{ fontSize: 26 }}>{thisWeekCount}</div>
          <div className="dash-stat-label" style={{ marginBottom: 10 }}>Transcriptions this week</div>
          <BarChart data={dayCounts} color="var(--d-blue)" />
          <div className="dash-bar-chart-labels">
            {dayLabels.map((l, i) => <span key={i}>{l}</span>)}
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Chart Analytics</h3>
              <p>By language</p>
            </div>
          </div>
          <div className="dash-donut-wrap">
            <DonutChart
              segments={[
                { label: 'English', value: englishCount, color: 'var(--d-blue)' },
                { label: 'Kinyarwanda', value: kinyarwandaCount, color: 'var(--d-purple)' },
              ]}
              centerLabel={records.length}
              centerSub="Total"
            />
            <div className="dash-donut-legend">
              <div className="dash-legend-item"><span className="dash-legend-dot" style={{ background: 'var(--d-blue)' }} /> English ({records.length ? Math.round((englishCount / records.length) * 100) : 0}%)</div>
              <div className="dash-legend-item"><span className="dash-legend-dot" style={{ background: 'var(--d-purple)' }} /> Kinyarwanda ({records.length ? Math.round((kinyarwandaCount / records.length) * 100) : 0}%)</div>
            </div>
          </div>
        </div>
      </div>

      {recentInWeek.length > 0 && (
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Recent Activity</h3>
              <p>Where this week's transcriptions landed</p>
            </div>
          </div>
          <div className="dash-timeline">
            {recentInWeek.map((r, i) => (
              <div key={r.id} className="dash-timeline-row">
                <span className="dash-timeline-label" title={r.filename}>{(r.filename || 'Untitled').slice(0, 14)}</span>
                <div className="dash-timeline-track">
                  <div
                    className="dash-timeline-bar"
                    style={{
                      left: `${(r.dayIndex / 7) * 100}%`,
                      width: `${(1 / 7) * 100}%`,
                      background: timelineColors[i % timelineColors.length],
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="dash-section-title">Overview</h2>
        <div className="dash-stats">
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-blue)' }}><ChatIcon /></div></div>
            <div className="dash-stat-value">{records.length}</div>
            <div className="dash-stat-label">Total Transcriptions</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-green)' }}><DocIcon /></div></div>
            <div className="dash-stat-value">{thisWeekCount}</div>
            <div className="dash-stat-label">This Week</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-purple)' }}><GlobeIcon /></div></div>
            <div className="dash-stat-value">{englishCount}</div>
            <div className="dash-stat-label">English</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-orange)' }}><GlobeIcon /></div></div>
            <div className="dash-stat-value">{kinyarwandaCount}</div>
            <div className="dash-stat-label">Kinyarwanda</div>
          </div>
        </div>
      </div>

      <div className="dash-row">
        <div className="dash-card" ref={profileRef}>
          <div className="dash-card-header">
            <div>
              <h3>My Profile</h3>
              <p>Keep your account details up to date</p>
            </div>
          </div>
          {msg && <div className="dash-alert">{msg}</div>}
          <form onSubmit={saveProfile}>
            <div className="dash-field">
              <label>Full name</label>
              <input placeholder="Full name" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} />
            </div>
            <div className="dash-field">
              <label>Department</label>
              <input placeholder="Department" value={profile.department} onChange={(e) => setProfile({ ...profile, department: e.target.value })} />
            </div>
            <div className="dash-field">
              <label>Phone</label>
              <input placeholder="Phone" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} />
            </div>
            <button className="dash-btn dash-btn-primary" type="submit">Save Profile</button>
          </form>

          <form onSubmit={saveLanguage} style={{ marginTop: 18 }}>
            <div className="dash-field">
              <label>Language</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="rw">Kinyarwanda</option>
              </select>
            </div>
            <button className="dash-btn" type="submit">Set Language</button>
          </form>

          <form onSubmit={uploadAvatar} style={{ marginTop: 18 }}>
            <div className="dash-field">
              <label>Avatar</label>
              <input type="file" accept="image/*" onChange={(e) => setAvatarFile(e.target.files[0])} />
            </div>
            <button className="dash-btn" type="submit">Upload</button>
          </form>
        </div>

        <div className="dash-card" ref={transcriptionsRef}>
          <div className="dash-card-header">
            <div>
              <h3>My Transcriptions</h3>
              <p>Recordings and files you've transcribed</p>
            </div>
          </div>
          {loading ? <div className="dash-empty">Loading...</div> : (
            <div className="dash-list">
              {records.length === 0 && <div className="dash-empty">No saved transcriptions</div>}
              {records.map(r => (
                <div key={r.id} className="dash-list-item">
                  <div>
                    <div className="dash-item-title">{r.filename}</div>
                    <span className="dash-badge">{r.language_detected === 'rw' ? 'Kinyarwanda' : 'English'}</span>
                  </div>
                  <div className="dash-item-actions">
                    <button className="dash-btn dash-btn-sm" onClick={() => window.open(`${API_URL}${r.audio_url || ''}`, '_blank')}>Play</button>
                    <button className="dash-btn dash-btn-sm dash-btn-danger" onClick={() => deleteRecord(r.id)}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default UserDashboard;
