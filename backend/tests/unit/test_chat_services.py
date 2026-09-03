import unittest

from app.services.intent_service import Intent, IntentRouter
from app.services.llm_service import DeterministicLLMService


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_uncertain_input_falls_back_to_chat(self):
        self.assertEqual(self.router.classify("How are you today?"), Intent.CHAT)

    def test_recognizes_supported_intents(self):
        self.assertEqual(self.router.classify("Translate this to Kinyarwanda"), Intent.TRANSLATION)
        self.assertEqual(self.router.classify("Create a quiz from these notes"), Intent.STUDY)
        self.assertEqual(self.router.classify("Please transcribe this recording"), Intent.SPEECH)


class DeterministicProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_completion_is_predictable(self):
        provider = DeterministicLLMService()
        result = await provider.complete([{"role": "user", "content": "Muraho"}])
        self.assertEqual(result, "EVA test response: Muraho")

    async def test_stream_reconstructs_completion(self):
        provider = DeterministicLLMService()
        messages = [{"role": "user", "content": "Hello"}]
        chunks = [chunk async for chunk in provider.stream(messages)]
        self.assertEqual("".join(chunks).strip(), await provider.complete(messages))
