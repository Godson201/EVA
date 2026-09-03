-- Create database
CREATE DATABASE IF NOT EXISTS audio_to_text;
USE audio_to_text;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Audio records table
CREATE TABLE IF NOT EXISTS audio_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INT DEFAULT 0,
    duration FLOAT DEFAULT 0,
    language_detected VARCHAR(10) DEFAULT 'unknown',
    original_text TEXT,
    summary_text TEXT,
    key_points JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_language (language_detected),
    INDEX idx_created (created_at),
    INDEX idx_user (user_id)
);

-- Insert a test user
INSERT INTO users (username, email, password_hash) 
VALUES ('demo_user', 'demo@example.com', 'demo_hash_placeholder')
ON DUPLICATE KEY UPDATE username=username;

-- Show tables
SHOW TABLES;

-- Show all records (should be empty initially)
SELECT * FROM audio_records;