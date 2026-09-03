import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from auth import authenticate_user, reset_user_password, is_valid_email, send_registration_email, register_user


class AuthTests(unittest.TestCase):
    def test_authenticate_user_accepts_email_identifier(self):
        user_row = {
            'id': 7,
            'username': 'demo',
            'email': 'demo@example.com',
            'password_hash': '$2b$12$abcdefghijklmnopqrstuv',
            'is_active': True,
        }

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row
        mock_conn.cursor.return_value = mock_cursor

        with patch('auth.verify_password', return_value=True), patch('auth.db.get_connection', return_value=mock_conn):
            user = authenticate_user('demo@example.com', 'secret123')

        self.assertEqual(user['id'], 7)
        self.assertEqual(user['username'], 'demo')
        mock_cursor.execute.assert_any_call(
            'SELECT * FROM users WHERE (username = %s OR email = %s) AND is_active = TRUE',
            ('demo@example.com', 'demo@example.com')
        )

    def test_reset_user_password_updates_existing_account(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 10}
        mock_conn.cursor.return_value = mock_cursor

        with patch('auth.db.get_connection', return_value=mock_conn):
            result = reset_user_password('user@example.com', 'new-pass-123')

        self.assertTrue(result['success'])
        self.assertIn('updated', result['message'].lower())

    def test_valid_email_format(self):
        self.assertTrue(is_valid_email('user@example.com'))
        self.assertFalse(is_valid_email('not-an-email'))

    def test_send_registration_email_uses_smtp(self):
        with patch('auth.smtplib.SMTP_SSL') as smtp_cls:
            smtp_instance = smtp_cls.return_value.__enter__.return_value
            smtp_instance.sendmail.return_value = None

            with patch.dict(os.environ, {
                'SMTP_EMAIL': 'capstonp003@gmail.com',
                'SMTP_PASSWORD': 'qvhf wgvr wyqr etqv'
            }, clear=False):
                result = send_registration_email('demo', 'demo@example.com', 'Secret123')

        self.assertTrue(result)
        smtp_instance.login.assert_called_once_with('capstonp003@gmail.com', 'qvhfwgvrwyqretqv')

    def test_register_user_accepts_provider(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 22
        mock_conn.cursor.return_value = mock_cursor

        with patch('auth.db.get_connection', return_value=mock_conn), patch('auth.get_password_hash', return_value='hash'), patch('auth.send_registration_email', return_value=True):
            user = register_user('demo', 'demo@example.com', 'Secret123', provider='google')

        self.assertEqual(user['provider'], 'google')


if __name__ == '__main__':
    unittest.main()
