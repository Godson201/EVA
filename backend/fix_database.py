import mysql.connector
from config import Config

def verify_and_fix():
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()
        
        print("=" * 60)
        print("DATABASE VERIFICATION")
        print("=" * 60)
        
        # Check audio_records structure
        cursor.execute("SHOW COLUMNS FROM audio_records")
        columns = cursor.fetchall()
        has_word_count = any(col[0] == 'word_count' for col in columns)
        
        if not has_word_count:
            print("⚠️ Adding word_count column...")
            cursor.execute("ALTER TABLE audio_records ADD COLUMN word_count INT DEFAULT 0 AFTER duration")
            conn.commit()
            print("✅ word_count column added")
        else:
            print("✅ word_count column exists")
        
        # Update word counts
        cursor.execute("""
            UPDATE audio_records 
            SET word_count = LENGTH(original_text) - LENGTH(REPLACE(original_text, ' ', '')) + 1
            WHERE original_text IS NOT NULL AND (word_count = 0 OR word_count IS NULL)
        """)
        conn.commit()
        print(f"✅ Updated {cursor.rowcount} records with word counts")
        
        # Check users table
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        active_users = cursor.fetchone()[0]
        print(f"✅ Active users: {active_users}")
        
        # Check total transcriptions
        cursor.execute("SELECT COUNT(*) FROM audio_records")
        total = cursor.fetchone()[0]
        print(f"✅ Total transcriptions: {total}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Database is ready for enhanced system!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    verify_and_fix()