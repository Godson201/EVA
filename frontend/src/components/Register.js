import React, { useState } from 'react';
import './Auth.css';

function Register({ onRegister, onSwitchToLogin }) {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    fullName: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState('email');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const providerOptions = [
    { id: 'email', label: 'Email', badge: 'E', accentClass: 'email' },
    { id: 'google', label: 'Continue with Google', badge: 'G', accentClass: 'google' },
    { id: 'microsoft', label: 'Continue with Microsoft', badge: 'M', accentClass: 'microsoft' },
    { id: 'facebook', label: 'Continue with Facebook', badge: 'f', accentClass: 'facebook' },
    { id: 'github', label: 'Continue with GitHub', badge: 'GH', accentClass: 'github' }
  ];

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
    setSuccessMessage('');
  };

  const validateForm = () => {
    if (formData.username.length < 3) {
      setError('Username must be at least 3 characters');
      return false;
    }
    
    if (formData.username.length > 50) {
      setError('Username must be less than 50 characters');
      return false;
    }
    
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(formData.email.trim())) {
      setError('Please enter a valid email address');
      return false;
    }
    
    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return false;
    }
    
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccessMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          username: formData.username.trim(), 
          email: formData.email.trim(), 
          password: formData.password, 
          full_name: formData.fullName.trim() || null,
          provider: selectedProvider
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        const providerLabel = providerOptions.find((item) => item.id === selectedProvider)?.label || 'Email';
        const emailNote = data.email_sent ? ' A welcome email has been sent to your inbox.' : ' The welcome email could not be sent right now.';
        const providerNote = selectedProvider === 'email' ? '' : ` You selected ${providerLabel} for sign-up.`;
        setSuccessMessage((data.message || `Account created for ${formData.username.trim()}. Please keep your password safe.`) + emailNote + providerNote);
        setSuccess(true);
        setTimeout(() => {
          onRegister();
        }, 2400);
      } else {
        setError(data.detail || 'Registration failed. Username or email may already exist.');
      }
    } catch (err) {
      console.error('Registration error:', err);
      setError('Network error. Please check if the server is running on port 8000');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-container">
        <div className="auth-card" style={{ textAlign: 'center' }}>
            <h2>Registration Successful!</h2>
          <p style={{ marginBottom: '12px' }}>
            Your account has been created. Redirecting to login...
          </p>
          <p style={{ marginBottom: '24px', color: '#0f766e', fontWeight: 600 }}>
            {successMessage || 'Please use your username or email with your password to sign in.'}
          </p>
          <div className="loading-spinner" style={{ margin: '20px auto' }}>
            <div className="spinner"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Create Account</h2>
        <p>Join AudioText Pro today</p>

        <div className="provider-buttons">
          {providerOptions.map((provider) => (
            <button
              key={provider.id}
              type="button"
              className={`provider-btn ${selectedProvider === provider.id ? 'active' : ''} ${provider.accentClass}`}
              onClick={() => {
                if (provider.id === 'google') {
                  window.location.href = 'http://localhost:8000/api/auth/oauth/google';
                  return;
                }
                setSelectedProvider(provider.id);
              }}
              disabled={loading}
            >
              <span className="provider-badge">{provider.badge}</span>
              <span className="provider-text">{provider.label}</span>
            </button>
          ))}
        </div>
        {selectedProvider !== 'email' && (
          <div className="info-message">Selected provider: {providerOptions.find((item) => item.id === selectedProvider)?.label}. OAuth sign-in will be enabled soon.</div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username *</label>
            <div className="input-icon">
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="Choose a username (min 3 characters)"
                required
                autoFocus
                disabled={loading}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Email *</label>
            <div className="input-icon">
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="your@email.com"
                required
                disabled={loading}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Full Name (Optional)</label>
            <div className="input-icon">
              <input
                type="text"
                name="fullName"
                value={formData.fullName}
                onChange={handleChange}
                placeholder="Your full name"
                disabled={loading}
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Password *</label>
            <div className="input-icon">
              <input
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Minimum 6 characters"
                required
                disabled={loading}
              />
              <button type="button" className="password-toggle-btn" onClick={() => setShowPassword((prev) => !prev)}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          
          <div className="form-group">
            <label>Confirm Password *</label>
            <div className="input-icon">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Confirm your password"
                required
                disabled={loading}
              />
              <button type="button" className="password-toggle-btn" onClick={() => setShowConfirmPassword((prev) => !prev)}>
                {showConfirmPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          
          {error && <div className="error-message">{error}</div>}
          {successMessage && <div className="success-message">{successMessage}</div>}
          
          <button type="submit" disabled={loading} className="auth-btn">
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>
        
        <p className="auth-switch">
          Already have an account?{' '}
          <button onClick={onSwitchToLogin} className="link-btn" disabled={loading}>
            Sign In
          </button>
        </p>
        
        <div className="auth-footer">
          <p>By creating an account, you agree to our terms of service</p>
        </div>
      </div>
    </div>
  );
}

export default Register;