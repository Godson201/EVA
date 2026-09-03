import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from app.repositories.conversations import ConversationRepository


class ConversationRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_lookup_filters_by_user_and_archived_state(self):
        session = MagicMock()
        session.scalar = AsyncMock(return_value=None)
        repository = ConversationRepository(session)
        await repository.get_owned(uuid.uuid4(), uuid.uuid4())
        statement = session.scalar.await_args.args[0]
        sql = str(statement)
        self.assertIn("conversations.user_id", sql)
        self.assertIn("conversations.archived_at IS NULL", sql)
