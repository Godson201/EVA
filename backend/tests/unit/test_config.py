import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_safe_for_lightweight_development(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.api_v1_prefix, "/api/v1")
        self.assertFalse(settings.legacy_app_enabled)

    def test_production_rejects_default_secret(self):
        with patch.dict(os.environ, {"EVA_ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None)

    def test_production_accepts_explicit_secret_and_origin(self):
        values = {
            "EVA_ENVIRONMENT": "production",
            "EVA_SECRET_KEY": "x" * 48,
            "EVA_CORS_ORIGINS": '["https://eva.example.com"]',
        }
        with patch.dict(os.environ, values, clear=True):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.cors_origins, ["https://eva.example.com"])
