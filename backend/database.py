import mysql.connector
from mysql.connector import pooling
import json
from config import Config
import os

class Database:
    def __init__(self):
        self.connection_pool = None
        self.setup_pool()
    
    def setup_pool(self):
        try:
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="audiotext_pool",
                pool_size=10,
                pool_reset_session=True,
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME
            )
            print("✅ Database connection pool created")
        except Exception as e:
            print(f"⚠️ Database pool error: {e}")
            print("Will use direct connections instead")
    
    def get_connection(self):
        """Get connection from pool or create direct connection"""
        if self.connection_pool:
            try:
                return self.connection_pool.get_connection()
            except Exception as e:
                print(f"Pool connection error: {e}")
        
        # Fallback to direct connection
        return mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
    
    def insert_record(self, filename, file_path, language, text, summary, key_points, user_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        word_count = len(text.split()) if text else 0
        
        query = """
            INSERT INTO audio_records 
            (user_id, filename, file_path, language_detected, original_text, summary_text, key_points, word_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (user_id, filename, file_path, language, text, summary, json.dumps(key_points), word_count)
        cursor.execute(query, values)
        conn.commit()
        record_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return record_id
    
    def get_all_records(self, user_id=None, include_all=False):
        """Get audio records - directors see all, others see only theirs"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if include_all:
            cursor.execute("SELECT * FROM audio_records ORDER BY created_at DESC")
        elif user_id:
            cursor.execute("SELECT * FROM audio_records WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM audio_records ORDER BY created_at DESC")
        
        records = cursor.fetchall()
        for record in records:
            if record.get('key_points'):
                try:
                    record['key_points'] = json.loads(record['key_points'])
                except:
                    record['key_points'] = []
        cursor.close()
        conn.close()
        return records
    
    def get_record_by_id(self, record_id, user_id=None):
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        if user_id:
            cursor.execute("SELECT * FROM audio_records WHERE id = %s AND user_id = %s", (record_id, user_id))
        else:
            cursor.execute("SELECT * FROM audio_records WHERE id = %s", (record_id,))
        record = cursor.fetchone()
        if record and record.get('key_points'):
            try:
                record['key_points'] = json.loads(record['key_points'])
            except:
                record['key_points'] = []
        cursor.close()
        conn.close()
        return record
    
    def delete_record(self, record_id, user_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("DELETE FROM audio_records WHERE id = %s AND user_id = %s", (record_id, user_id))
        else:
            cursor.execute("DELETE FROM audio_records WHERE id = %s", (record_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        conn.close()
        return deleted
    
    def get_all_users(self):
        """Get all users (for directors)"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, full_name, role, department, phone, is_active, created_at, last_active FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return users
    
    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, full_name, role, department, phone, is_active, created_at, last_active FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    
    def update_user_status(self, user_id, is_active):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (is_active, user_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        return affected > 0
    
    def get_system_stats(self):
        """Get system statistics for director dashboard"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Total transcriptions
        cursor.execute("SELECT COUNT(*) as total FROM audio_records")
        total_transcriptions = cursor.fetchone()['total']
        
        # Total users
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        # Active users (logged in within last 7 days)
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE last_active > DATE_SUB(NOW(), INTERVAL 7 DAY)")
        active_users = cursor.fetchone()['total'] if total_users > 0 else 0
        
        # Transcriptions by language
        cursor.execute("SELECT language_detected, COUNT(*) as count FROM audio_records GROUP BY language_detected")
        by_language = cursor.fetchall()
        
        # Total words transcribed
        cursor.execute("SELECT SUM(word_count) as total FROM audio_records")
        total_words = cursor.fetchone()['total'] or 0
        
        # Transcriptions by user
        cursor.execute("""
            SELECT u.username, u.full_name, u.role, COUNT(a.id) as count, COALESCE(SUM(a.word_count), 0) as total_words 
            FROM users u 
            LEFT JOIN audio_records a ON u.id = a.user_id 
            GROUP BY u.id 
            ORDER BY count DESC
        """)
        by_user = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            "total_transcriptions": total_transcriptions,
            "total_users": total_users,
            "active_users": active_users,
            "total_words": total_words,
            "by_language": by_language,
            "by_user": by_user
        }

# Create the database instance
db = Database()

# Test the connection
if __name__ == "__main__":
    try:
        conn = db.get_connection()
        print("✅ Database connection successful!")
        conn.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\nPlease ensure:")
        print("1. MySQL/XAMPP is running")
        print("2. Database 'audio_to_text' exists")
        print("3. Run the SQL schema to create tables")