import logging
from typing import Any, Callable

from app.core.keywords import is_music_title
from app.models.chat import OwnedChat
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.chat_search")


class ChatSearchHandler:
    """Manages asynchronous Telegram chat searching, details aggregation, and filtering."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        get_owned_chat: Callable[[int], OwnedChat | None],
        get_supergroup: Callable[[int], dict[str, Any] | None],
        get_basic_group: Callable[[int], dict[str, Any] | None],
        register_owned_chat: Callable[[OwnedChat], None],
        on_search_results: Callable[[list[OwnedChat]], None],
    ) -> None:
        self._adapter = adapter
        self._get_owned_chat = get_owned_chat
        self._get_supergroup = get_supergroup
        self._get_basic_group = get_basic_group
        self._register_owned_chat = register_owned_chat
        self._on_search_results = on_search_results

        self._search_accumulator: dict[str, list[OwnedChat]] = {}
        self._search_pending: dict[str, set[int]] = {}

    def search_chats(self, query: str, limit: int = 100) -> None:
        if not query.strip():
            return

        search_id = f"search_chats_{id(self)}_{len(self._search_accumulator)}"
        self._search_accumulator[search_id] = []
        self._search_pending[search_id] = set()

        self._adapter.send({
            "@type": "searchChats",
            "query": query.strip(),
            "limit": limit,
            "@extra": search_id,
        })
        logger.debug("Searching chats with query='%s', search_id='%s'", query, search_id)

    def process_search_results(self, chat_ids: list[int], search_id: str) -> None:
        if not chat_ids:
            self._on_search_results([])
            self._cleanup_search(search_id)
            return

        self._search_pending[search_id] = set(chat_ids)
        self._search_accumulator[search_id] = []

        for chat_id in chat_ids:
            self._adapter.send({
                "@type": "getChat",
                "chat_id": chat_id,
                "@extra": f"search_chat_details_{search_id}_{chat_id}",
            })

    def process_chat_details(self, search_id: str, chat_id: int, chat: dict[str, Any]) -> None:
        owned = self._get_owned_chat(chat_id)
        if owned:
            if search_id in self._search_accumulator:
                self._search_accumulator[search_id].append(owned)
            if search_id in self._search_pending:
                self._search_pending[search_id].discard(chat_id)
            self._check_search_completion(search_id)
            return

        chat_type = chat.get("type", {})
        type_str = chat_type.get("@type", "")
        title = chat.get("title", "")

        if type_str == "chatTypeSupergroup":
            sg_id = chat_type.get("supergroup_id", 0)
            sg = self._get_supergroup(sg_id)
            if sg:
                status = sg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or sg.get("is_creator", False):
                    if is_music_title(title):
                        new_owned = OwnedChat(
                            id=chat_id,
                            title=title,
                            is_channel=sg.get("is_channel", True),
                            supergroup_id=sg_id,
                            unread_count=chat.get("unread_count", 0),
                        )
                        self._register_owned_chat(new_owned)
                        if search_id in self._search_accumulator:
                            self._search_accumulator[search_id].append(new_owned)
            else:
                self._adapter.send({
                    "@type": "getSupergroup",
                    "supergroup_id": sg_id,
                    "@extra": f"check_supergroup_{chat_id}",
                })
                return

        elif type_str == "chatTypeBasicGroup":
            bg_id = chat_type.get("basic_group_id", 0)
            bg = self._get_basic_group(bg_id)
            if bg:
                status = bg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or bg.get("is_creator", False):
                    if is_music_title(title):
                        new_owned = OwnedChat(
                            id=chat_id,
                            title=title,
                            is_channel=False,
                            supergroup_id=0,
                            unread_count=chat.get("unread_count", 0),
                        )
                        self._register_owned_chat(new_owned)
                        if search_id in self._search_accumulator:
                            self._search_accumulator[search_id].append(new_owned)
            else:
                self._adapter.send({
                    "@type": "getBasicGroup",
                    "basic_group_id": bg_id,
                    "@extra": f"check_basicgroup_{chat_id}",
                })
                return

        if search_id in self._search_pending:
            self._search_pending[search_id].discard(chat_id)
        self._check_search_completion(search_id)

    def _check_search_completion(self, search_id: str) -> None:
        if search_id not in self._search_pending:
            return

        if not self._search_pending[search_id]:
            results = self._search_accumulator.get(search_id, [])
            logger.debug("Search completed with %d results", len(results))
            self._on_search_results(results)
            self._cleanup_search(search_id)

    def _cleanup_search(self, search_id: str) -> None:
        self._search_accumulator.pop(search_id, None)
        self._search_pending.pop(search_id, None)