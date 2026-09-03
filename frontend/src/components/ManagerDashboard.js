import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import DashboardLayout from './DashboardLayout';
import { BarChart, DonutChart } from './DashCharts';

const API_URL = 'http://localhost:8000';

const DocIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
);
const ChartIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="M18 9l-5 5-3-3-4 4"/></svg>
);
const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 4 5v6c0 5 3.5 8.5 8 11 4.5-2.5 8-6 8-11V5z"/></svg>
);

function ManagerDashboard({ user, onClose, onLogout }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);

  const recordsRef = useRef(null);
  const chartsRef = useRef(null);
  const roleRef = useRef(null);

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
      setMessage('Failed to load records');
    } finally {
      setLoading(false);
    }
  };

  const deleteRecord = async (id, filename) => {
    if (!window.confirm(`Delete "${filename}"?`)) return;
    try {
      await api.delete(`/record/${id}`);
      setMessage('Record deleted');
      fetchRecords();
    } catch (err) {
      console.error(err);
      setMessage('Delete failed');
    }
  };

  const scrollTo = (ref) => ref.current && ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const englishCount = records.filter(r => r.language_detected === 'en').length;
  const kinyarwandaCount = records.filter(r => r.language_detected === 'rw').length;

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

  return (
    <DashboardLayout user={user} onClose={onClose} onLogout={onLogout}>
      <div className="dash-hero">
        <h1>Welcome back, {(user && (user.full_name || user.username)) || 'Manager'}! 👋</h1>
        <p>Here's what's happening across your workspace</p>
      </div>

      <div>
        <h2 className="dash-section-title">Quick Actions</h2>
        <div className="dash-quick-actions">
          <button className="dash-quick-tile" onClick={() => scrollTo(recordsRef)}>
            <div className="dash-quick-icon blue"><DocIcon /></div>
            <div className="dash-quick-title">Workspace Records</div>
            <div className="dash-quick-sub">Review, play or remove transcriptions</div>
            <div className="dash-quick-arrow">→</div>
          </button>
          <button className="dash-quick-tile" onClick={() => scrollTo(chartsRef)}>
            <div className="dash-quick-icon green"><ChartIcon /></div>
            <div className="dash-quick-title">Statistics</div>
            <div className="dash-quick-sub">Usage over the last 7 days</div>
            <div className="dash-quick-arrow">→</div>
          </button>
          <button className="dash-quick-tile" onClick={() => scrollTo(roleRef)}>
            <div className="dash-quick-icon purple"><ShieldIcon /></div>
            <div className="dash-quick-title">Role &amp; Access</div>
            <div className="dash-quick-sub">Your workspace oversight permissions</div>
            <div className="dash-quick-arrow">→</div>
          </button>
        </div>
      </div>

      <div className="dash-charts-row" ref={chartsRef}>
        <div className="dash-card">
          <div className="dash-card-header">
            <div>
              <h3>Usage Overview</h3>
              <p>Last 7 days</p>
            </div>
          </div>
          <div className="dash-stat-value" style={{ fontSize: 26 }}>{thisWeekCount}</div>
          <div className="dash-stat-label" style={{ marginBottom: 10 }}>Records this week</div>
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

      <div>
        <h2 className="dash-section-title">Overview</h2>
        <div className="dash-stats">
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-blue)' }}><DocIcon /></div></div>
            <div className="dash-stat-value">{records.length}</div>
            <div className="dash-stat-label">Workspace Records</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-icon-row"><div className="dash-stat-icon" style={{ background: 'var(--d-green)' }}><ChartIcon /></div></div>
            <div className="dash-stat-value">{thisWeekCount}</div>
            <div className="dash-stat-label">This Week</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-value">{englishCount}</div>
            <div className="dash-stat-label">English</div>
          </div>
          <div className="dash-stat">
            <div className="dash-stat-value">{kinyarwandaCount}</div>
            <div className="dash-stat-label">Kinyarwanda</div>
          </div>
        </div>
      </div>

      <div className="dash-card" ref={roleRef}>
        <div className="dash-card-header">
          <div>
            <h3>Manager Dashboard</h3>
            <p>Role: Manager — limited workspace oversight</p>
          </div>
        </div>
      </div>

      <div className="dash-card" ref={recordsRef}>
        <div className="dash-card-header">
          <div>
            <h3>Your Workspace Records</h3>
            <p>All transcriptions available to your workspace</p>
          </div>
        </div>
        {message && <div className="dash-alert">{message}</div>}
        {loading ? <div className="dash-empty">Loading...</div> : (
          <div className="dash-list">
            {records.length === 0 && <div className="dash-empty">No records available</div>}
            {records.map(r => (
              <div key={r.id} className="dash-list-item">
                <div>
                  <div className="dash-item-title">{r.filename}</div>
                  <div className="dash-item-sub">{r.user_id ? `By ${r.user_id}` : 'Unknown'} • {r.language_detected === 'rw' ? 'Kinyarwanda' : 'English'}</div>
                </div>
                <div className="dash-item-actions">
                  <button className="dash-btn dash-btn-sm" onClick={() => window.open(`${API_URL}${r.audio_url || ''}`, '_blank')}>Play</button>
                  <button className="dash-btn dash-btn-sm dash-btn-danger" onClick={() => deleteRecord(r.id, r.filename)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

    </DashboardLayout>
  );
}

export default ManagerDashboard;
