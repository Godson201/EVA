import os

class Config:
    # Database Configuration for XAMPP
    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWORD = ''  # XAMPP default has no password
    DB_NAME = 'audio_to_text'
    
    # Directories
    TEMP_DIR = 'temp'
    UPLOAD_DIR = 'uploads'
    
    # Audio settings
    ALLOWED_AUDIO_TYPES = [
        'audio/mpeg', 'audio/wav', 'audio/mp3', 
        'audio/m4a', 'audio/ogg', 'audio/x-m4a',
        'audio/webm', 'audio/x-wav'
    ]
    
    # Model settings
    WHISPER_MODEL_SIZE = 'base'

# Create directories
os.makedirs(Config.TEMP_DIR, exist_ok=True)
os.makedirs(Config.UPLOAD_DIR, exist_ok=True)