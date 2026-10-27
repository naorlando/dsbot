import unittest

from core.assistant_memory import ConversationMemory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.memory = ConversationMemory(max_sessions=2, clock=lambda: self.now)

    def test_ten_messages_bounded_and_no_disk(self):
        for i in range(20):
            self.memory.remember((1, 2, 3), str(i), "respuesta " + str(i))
        messages = self.memory.read((1, 2, 3))
        self.assertEqual(len(messages), 10)
        self.assertEqual(messages[-1]["content"], "respuesta 19")

    def test_idle_expiration(self):
        self.memory.remember((1, 2, 3), "hola", "hola")
        self.now = 1799
        self.assertEqual(len(self.memory.read((1, 2, 3))), 2)
        self.now = 1800
        self.assertEqual(self.memory.read((1, 2, 3)), [])

    def test_sessions_bounded_and_isolated(self):
        for key in ((1, 2, 3), (1, 2, 4), (1, 5, 3)):
            self.memory.remember(key, str(key), "hola")
        self.assertEqual(self.memory.read((1, 2, 3)), [])
        self.assertEqual(len(self.memory.sessions), 2)
        self.assertEqual(self.memory.read((2, 2, 4)), [])

    def test_forget_only_owner_and_copy_on_read(self):
        self.memory.remember((1, 2, 3), "hola", "hola")
        self.memory.remember((1, 2, 4), "otro", "otro")
        self.memory.read((1, 2, 4))[0]["content"] = "changed"
        self.memory.forget((1, 2, 3))
        self.assertEqual(self.memory.read((1, 2, 3)), [])
        self.assertEqual(self.memory.read((1, 2, 4))[0]["content"], "otro")

    def test_message_size_and_question_only_private_turn(self):
        self.memory.remember((1, 2, 3), "x" * 1000, "secret" * 1000, private=True)
        messages = self.memory.read((1, 2, 3))
        self.assertEqual(len(messages[0]["content"]), 800)
        # Private turns are question-only: no answer, no placeholder note to recite.
        self.assertEqual(len(messages), 1)
        self.assertNotIn("secret", str(messages))

    def test_web_turn_is_question_only(self):
        self.memory.remember((1, 2, 3), "cuanto cerro el dolar")
        messages = self.memory.read((1, 2, 3))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "cuanto cerro el dolar")
        # Full turns (public answers) still keep both sides of the chat, appended
        # onto the same session: the old question-only turn leaves no fake reply.
        self.memory.remember((1, 2, 3), "otra", "otra respuesta")
        messages = self.memory.read((1, 2, 3))
        self.assertEqual([m["role"] for m in messages], ["user", "user", "assistant"])
        self.assertEqual(messages[-1]["content"], "otra respuesta")

    def test_unscoped_requests_not_remembered(self):
        self.memory.remember(None, "hola", "hola")
        self.assertEqual(self.memory.read(None), [])
        self.assertEqual(len(self.memory.sessions), 0)
