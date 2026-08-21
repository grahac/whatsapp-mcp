import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import main
from whatsapp import Chat, Contact, Message, MessageContext


class ToolOutputContractTest(unittest.IsolatedAsyncioTestCase):
    async def call_tool(self, name, arguments=None):
        result = await main.mcp.call_tool(name, arguments or {})
        if isinstance(result, tuple):
            content, structured_content = result
            return SimpleNamespace(
                content=content, structured_content=structured_content
            )
        return result

    async def test_search_contacts_serializes_contacts(self):
        contact = Contact("15551234567", "Test Contact", "15551234567@s.whatsapp.net")

        with patch.object(main, "whatsapp_search_contacts", return_value=[contact]):
            result = await self.call_tool("search_contacts", {"query": "Test"})

        self.assertEqual(
            result.structured_content,
            {
                "result": [
                    {
                        "phone_number": "15551234567",
                        "name": "Test Contact",
                        "jid": "15551234567@s.whatsapp.net",
                    }
                ]
            },
        )

    async def test_list_messages_preserves_formatted_text(self):
        formatted = "[2026-08-20 09:00:00] From: Me: Lunch at noon?\n"

        with patch.object(main, "whatsapp_list_messages", return_value=formatted):
            result = await self.call_tool(
                "list_messages",
                {"query": "lunch", "limit": 5, "include_context": False},
            )

        self.assertEqual(result.content[0].text, formatted)
        self.assertEqual(result.structured_content, {"result": formatted})

    async def test_list_chats_serializes_chats(self):
        chat = self.chat()

        with patch.object(main, "whatsapp_list_chats", return_value=[chat]):
            result = await self.call_tool("list_chats", {"limit": 1})

        self.assertEqual(result.structured_content["result"][0]["jid"], chat.jid)
        self.assertEqual(
            result.structured_content["result"][0]["last_message_time"],
            "2026-08-20T09:00:00",
        )

    async def test_single_chat_tools_serialize_chat_or_none(self):
        chat = self.chat()

        for tool_name, dependency_name, arguments in [
            ("get_chat", "whatsapp_get_chat", {"chat_jid": chat.jid}),
            (
                "get_direct_chat_by_contact",
                "whatsapp_get_direct_chat_by_contact",
                {"sender_phone_number": "15551234567"},
            ),
        ]:
            with self.subTest(tool_name=tool_name, found=True):
                with patch.object(main, dependency_name, return_value=chat):
                    result = await self.call_tool(tool_name, arguments)
                self.assertEqual(result.structured_content["result"]["jid"], chat.jid)

            with self.subTest(tool_name=tool_name, found=False):
                with patch.object(main, dependency_name, return_value=None):
                    result = await self.call_tool(tool_name, arguments)
                self.assertEqual(result.structured_content, {"result": None})

    async def test_get_contact_chats_serializes_chats(self):
        chat = self.chat()

        with patch.object(main, "whatsapp_get_contact_chats", return_value=[chat]):
            result = await self.call_tool("get_contact_chats", {"jid": chat.jid})

        self.assertEqual(result.structured_content["result"][0]["jid"], chat.jid)

    async def test_get_last_interaction_accepts_text_or_none(self):
        for value in ["Last message\n", None]:
            with self.subTest(value=value):
                with patch.object(main, "whatsapp_get_last_interaction", return_value=value):
                    result = await self.call_tool(
                        "get_last_interaction", {"jid": "15551234567@s.whatsapp.net"}
                    )
                self.assertEqual(result.structured_content, {"result": value})

    async def test_get_message_context_serializes_nested_messages(self):
        message = Message(
            timestamp=datetime(2026, 8, 20, 9, 0, 0),
            sender="15551234567@s.whatsapp.net",
            content="Lunch?",
            is_from_me=False,
            chat_jid="15551234567@s.whatsapp.net",
            id="message-1",
            chat_name="Test Contact",
        )
        context = MessageContext(message=message, before=[], after=[])

        with patch.object(main, "whatsapp_get_message_context", return_value=context):
            result = await self.call_tool(
                "get_message_context", {"message_id": message.id}
            )

        self.assertEqual(
            result.structured_content["result"]["message"]["id"], message.id
        )

    @staticmethod
    def chat():
        return Chat(
            jid="15551234567@s.whatsapp.net",
            name="Test Contact",
            last_message_time=datetime(2026, 8, 20, 9, 0, 0),
            last_message="Lunch?",
            last_sender="15551234567@s.whatsapp.net",
            last_is_from_me=False,
        )


if __name__ == "__main__":
    unittest.main()
