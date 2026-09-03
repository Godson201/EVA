import React, { useState, useEffect } from 'react';
import './Auth.css';

function Login({ onLogin, onSwitchToRegister, error: propError }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showRegisterOptions, setShowRegisterOptions] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('email');
  const [resetIdentifier, setResetIdentifier] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMessage, setResetMessage] = useState('');
  const providerOptions = [
    { id: 'email', label: 'Email', badge: 'E', accentClass: 'email' },
    { id: 'google', label: 'Continue with Google', badge: 'G', accentClass: 'google', logo: 'G' },
    { id: 'microsoft', label: 'Continue with Microsoft', badge: '◻', accentClass: 'microsoft', logo: 'W' },
    { id: 'facebook', label: 'Continue with Facebook', badge: 'f', accentClass: 'facebook', logo: 'f' },
    { id: 'github', label: 'Continue with GitHub', badge: 'GH', accentClass: 'github', logo: '⌘' }
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!username.trim()) {
      setError('Please enter your username');
      return;
    }
    
    if (!password) {
      setError('Please enter your password');
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccessMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        setSuccessMessage(data.message || `Welcome back, ${data.user.username}!`);
        onLogin(data.user);
      } else {
        setError(data.detail || 'Invalid username or password');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Network error. Please check if the server is running on port 8000');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async (e) => {
    e.preventDefault();
    if (!resetIdentifier.trim()) {
      setResetMessage('Please enter your username or email');
      return;
    }
    if (!resetPassword || resetPassword.length < 6) {
      setResetMessage('New password must be at least 6 characters');
      return;
    }

    setResetLoading(true);
    setResetMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/auth/password/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: resetIdentifier.trim(), new_password: resetPassword })
      });

      const data = await response.json();
      if (response.ok && data.success) {
        setResetMessage(data.message || 'Password reset complete. Please sign in with your new password.');
        setResetIdentifier('');
        setResetPassword('');
        setShowReset(false);
      } else {
        setResetMessage(data.detail || 'Unable to reset password');
      }
    } catch (err) {
      console.error('Password reset error:', err);
      setResetMessage('Network error. Please try again.');
    } finally {
      setResetLoading(false);
    }
  };

  useEffect(() => {
    // If the backend set an httpOnly cookie after OAuth, attempt to fetch current user
    const trySession = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/auth/me', { credentials: 'include' });
        const data = await res.json();
        if (res.ok && data.success && data.user) {
          // Notify parent that we have a logged-in user
          onLogin(data.user);
        }
      } catch (err) {
        // ignore
      }
    };

    trySession();
  }, []);

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Welcome back</h2>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username or Email</label>
            <div className="input-icon">
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username or email"
                required
                autoFocus
                disabled={loading}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <div className="input-icon">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                disabled={loading}
              />
              <button type="button" className="password-toggle-btn" onClick={() => setShowPassword((prev) => !prev)}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          
          {(error || propError) && (
            <div className="error-message">
              {error || propError}
            </div>
          )}
          {successMessage && <div className="success-message">{successMessage}</div>}
          {resetMessage && <div className={resetMessage.includes('success') || resetMessage.includes('Please sign in') ? 'success-message' : 'error-message'}>{resetMessage}</div>}
          
          <button type="submit" disabled={loading} className="auth-btn primary-green">
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        
        {/* Sign-up / provider area - hidden until user expands */}
        <div className="register-section" style={{ display: showRegisterOptions ? 'block' : 'none' }}>
          <p className="register-title">Create an account</p>
          <div className="separator"><span>or</span></div>
          <div className="register-provider-buttons">
            {providerOptions.filter((provider) => provider.id !== 'email').map((provider) => (
              <button
                key={provider.id}
                type="button"
                className={`register-provider-btn ${provider.accentClass}`}
                onClick={() => {
                  if (provider.id === 'google') {
                    // start Google OAuth flow via backend
                    window.location.href = 'http://localhost:8000/api/auth/oauth/google';
                    return;
                  }
                  setSelectedProvider(provider.id);
                  onSwitchToRegister();
                }}
                disabled={loading}
              >
                <span className={`provider-logo ${provider.accentClass}`}>
                  {provider.logo || provider.badge}
                </span>
                <span className="provider-text">{provider.label}</span>
              </button>
            ))}
          </div>
          <button onClick={() => { setShowRegisterOptions(false); onSwitchToRegister(); }} className="link-btn" disabled={loading}>
            Continue to full sign-up
          </button>
        </div>

        <p className="auth-switch" style={{ marginTop: '12px' }}>
          Don't have an account?{' '}
          <button onClick={() => setShowRegisterOptions((s) => !s)} className="link-btn" disabled={loading}>
            {showRegisterOptions ? 'Hide options' : 'Create account'}
          </button>
        </p>

        <p className="auth-switch" style={{ marginTop: '8px' }}>
          <button onClick={() => setShowReset((prev) => !prev)} className="link-btn" disabled={loading}>
            {showReset ? 'Hide password reset' : 'Forgot password?'}
          </button>
        </p>

        {showReset && (
          <form onSubmit={handlePasswordReset} style={{ marginTop: '16px' }}>
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>Username or Email</label>
              <div className="input-icon">
                <input
                  type="text"
                  value={resetIdentifier}
                  onChange={(e) => setResetIdentifier(e.target.value)}
                  placeholder="Enter your username or email"
                  required
                  disabled={resetLoading}
                />
              </div>
            </div>
            <div className="form-group" style={{ marginBottom: '16px' }}>
              <label>New Password</label>
              <div className="input-icon">
                <input
                  type={showResetPassword ? 'text' : 'password'}
                  value={resetPassword}
                  onChange={(e) => setResetPassword(e.target.value)}
                  placeholder="Choose a new password"
                  required
                  disabled={resetLoading}
                />
                <button type="button" className="password-toggle-btn" onClick={() => setShowResetPassword((prev) => !prev)}>
                  {showResetPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>
            <button type="submit" disabled={resetLoading} className="auth-btn">
              {resetLoading ? 'Updating password...' : 'Reset Password'}
            </button>
          </form>
        )}
        
        <div className="auth-footer">
          <p>Secure access for authorized personnel only</p>
          <p style={{ fontSize: '10px', marginTop: '8px' }}>AudioText Pro v9.0</p>
        </div>
      </div>
    </div>
  );
}

export default Login;