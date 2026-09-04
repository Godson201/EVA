import unittest

from pgvector.sqlalchemy import VECTOR

from app.db.base import Base
from app.migration.legacy_mysql import ROLE_MAP, stable_uuid
import app.models  # noqa: F401


class DatabaseModelTests(unittest.TestCase):
    def test_required_v2_tables_are_registered(self):
        expected = {
            "users", "refresh_tokens", "conversations", "messages", "attachments",
            "documents", "document_chunks", "transcriptions", "translations",
            "voice_profiles", "memories", "user_preferences", "vocabulary_items", "activity_logs",
            "processing_jobs", "study_artifacts",
        }
        self.assertEqual(expected, set(Base.metadata.tables))

    def test_vector_columns_have_fixed_dimensions(self):
        chunks = Base.metadata.tables["document_chunks"]
        memories = Base.metadata.tables["memories"]
        self.assertIsInstance(chunks.c.embedding.type, VECTOR)
        self.assertEqual(chunks.c.embedding.type.dim, 768)
        self.assertEqual(memories.c.embedding.type.dim, 768)

    def test_legacy_ids_are_stable_and_source_scoped(self):
        self.assertEqual(stable_uuid("audio_records", 7), stable_uuid("audio_records", 7))
        self.assertNotEqual(stable_uuid("audio_records", 7), stable_uuid("speech_recordings", 7))

    def test_legacy_role_mapping_is_explicit(self):
        self.assertEqual(ROLE_MAP["director"], "ADMIN")
        self.assertEqual(ROLE_MAP["manager"], "ADMIN")
