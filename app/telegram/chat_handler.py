import logging
from typing import Any, Callable

from app.core.keywords import is_music_title
from app.models.chat import OwnedChat
from app.settings.service import SettingsService
from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.telegram.chats")


class ChatHandler:
    """Handles channel discovery, stream loading, ownership checks, and chat deletions."""

    def __init__(
        self,
        adapter: TDLibAdapter,
        settings_service: SettingsService | None,
        on_owned_chats_updated: Callable[[list[OwnedChat]], None],
        on_search_results: Callable[[list[OwnedChat]], None],
    ) -> None:
        self._adapter = adapter
        self._settings = settings_service
        self._on_owned_chats_updated = on_owned_chats_updated
        self._on_search_results = on_search_results

        self._raw_chats: dict[int, dict[str, Any]] = {}
        self._supergroups: dict[int, dict[str, Any]] = {}
        self._basic_groups: dict[int, dict[str, Any]] = {}
        self._owned_chats: dict[int, OwnedChat] = {}

        # Search accumulators
        self._search_accumulator: dict[str, list[OwnedChat]] = {}
        self._search_pending: dict[str, set[int]] = {}

    def set_settings_service(self, settings_service: SettingsService) -> None:
        self._settings = settings_service

    # ------------------------------------------------------------------
    # Load cached chats
    # ------------------------------------------------------------------

    def load_cached_chats(self) -> None:
        if self._settings:
            cached = self._settings.get_cached_music_chats()
            if cached:
                for c in cached:
                    self._owned_chats[c.id] = c
                logger.info("Loaded %d music channels from local cache ⚡", len(cached))
                self._on_owned_chats_updated(list(self._owned_chats.values()))

    # ------------------------------------------------------------------
    # Start chat sync
    # ------------------------------------------------------------------

    def start_chat_sync(self) -> None:
        self._adapter.send({"@type": "getMe"})
        self._adapter.send({
            "@type": "getCreatedPublicChats",
            "type": {"@type": "publicChatTypeHasUsername"},
        })
        self._load_next_main_chats()

    def _load_next_main_chats(self) -> None:
        self._adapter.send({
            "@type": "loadChats",
            "chat_list": {"@type": "chatListMain"},
            "limit": 100,
            "@extra": "load_main_chats",
        })

    def _load_next_archive_chats(self) -> None:
        self._adapter.send({
            "@type": "loadChats",
            "chat_list": {"@type": "chatListArchive"},
            "limit": 100,
            "@extra": "load_archive_chats",
        })

    def handle_pagination_response(self, extra: str, update_type: str) -> None:
        if extra == "load_main_chats":
            if update_type == "ok":
                self._load_next_main_chats()
            elif update_type == "error":
                self._load_next_archive_chats()

        elif extra == "load_archive_chats":
            if update_type == "ok":
                self._load_next_archive_chats()

    # ------------------------------------------------------------------
    # Full search for chats
    # ------------------------------------------------------------------

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
        logger.info("Searching chats with query='%s', search_id='%s'", query, search_id)

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

    def process_chat_details_from_search(self, search_id: str, chat_id: int, chat: dict[str, Any]) -> None:
        # Check if already owned
        if chat_id in self._owned_chats:
            if search_id in self._search_accumulator:
                self._search_accumulator[search_id].append(self._owned_chats[chat_id])
            if search_id in self._search_pending:
                self._search_pending[search_id].discard(chat_id)
            self._check_search_completion(search_id)
            return

        # Store raw chat
        self._raw_chats[chat_id] = chat

        # Evaluate ownership
        chat_type = chat.get("type", {})
        type_str = chat_type.get("@type", "")
        title = chat.get("title", "")

        if type_str == "chatTypeSupergroup":
            sg_id = chat_type.get("supergroup_id", 0)
            if sg_id in self._supergroups:
                sg = self._supergroups[sg_id]
                if sg.get("status", {}).get("@type") == "chatMemberStatusCreator" or sg.get("is_creator", False):
                    if is_music_title(title):
                        owned = OwnedChat(
                            id=chat_id,
                            title=title,
                            is_channel=sg.get("is_channel", True),
                            supergroup_id=sg_id,
                            unread_count=chat.get("unread_count", 0),
                        )
                        self._owned_chats[chat_id] = owned
                        if search_id in self._search_accumulator:
                            self._search_accumulator[search_id].append(owned)
            else:
                self._adapter.send({
                    "@type": "getSupergroup",
                    "supergroup_id": sg_id,
                    "@extra": f"check_supergroup_{chat_id}",
                })
                # Keep pending until supergroup processed
                return

        elif type_str == "chatTypeBasicGroup":
            bg_id = chat_type.get("basic_group_id", 0)
            if bg_id in self._basic_groups:
                bg = self._basic_groups[bg_id]
                if bg.get("status", {}).get("@type") == "chatMemberStatusCreator" or bg.get("is_creator", False):
                    if is_music_title(title):
                        owned = OwnedChat(
                            id=chat_id,
                            title=title,
                            is_channel=False,
                            supergroup_id=0,
                            unread_count=chat.get("unread_count", 0),
                        )
                        self._owned_chats[chat_id] = owned
                        if search_id in self._search_accumulator:
                            self._search_accumulator[search_id].append(owned)
            else:
                self._adapter.send({
                    "@type": "getBasicGroup",
                    "basic_group_id": bg_id,
                    "@extra": f"check_basicgroup_{chat_id}",
                })
                return

        # Remove from pending and check completion
        if search_id in self._search_pending:
            self._search_pending[search_id].discard(chat_id)
        self._check_search_completion(search_id)

    def _check_search_completion(self, search_id: str) -> None:
        if search_id not in self._search_pending:
            return

        if not self._search_pending[search_id]:
            results = self._search_accumulator.get(search_id, [])
            logger.info("Search completed with %d results", len(results))
            self._on_search_results(results)
            self._cleanup_search(search_id)

    def _cleanup_search(self, search_id: str) -> None:
        self._search_accumulator.pop(search_id, None)
        self._search_pending.pop(search_id, None)

    # ------------------------------------------------------------------
    # Chat processing (existing)
    # ------------------------------------------------------------------

    def process_new_chat(self, chat: dict[str, Any]) -> None:
        chat_id = chat.get("id", 0)
        self._raw_chats[chat_id] = chat
        self._evaluate_chat_ownership(chat_id)

    def process_supergroup_update(self, sg: dict[str, Any]) -> None:
        sg_id = sg.get("id", 0)
        self._supergroups[sg_id] = sg

        status = sg.get("status", {}).get("@type", "")
        is_creator = status == "chatMemberStatusCreator" or sg.get("is_creator", False)

        if not is_creator:
            removed = False
            for chat_id, chat in list(self._raw_chats.items()):
                if chat.get("type", {}).get("supergroup_id") == sg_id:
                    if chat_id in self._owned_chats:
                        del self._owned_chats[chat_id]
                        removed = True
                        logger.info("🗑️ Removed deleted/left channel from owned chats: ID %d", chat_id)
            if removed:
                self._sync_and_emit()
            return

        for chat_id, chat in self._raw_chats.items():
            if chat.get("type", {}).get("supergroup_id") == sg_id:
                self._evaluate_chat_ownership(chat_id)

    def process_basic_group_update(self, bg: dict[str, Any]) -> None:
        bg_id = bg.get("id", 0)
        self._basic_groups[bg_id] = bg

        status = bg.get("status", {}).get("@type", "")
        is_creator = status == "chatMemberStatusCreator" or bg.get("is_creator", False)

        if not is_creator:
            removed = False
            for chat_id, chat in list(self._raw_chats.items()):
                if chat.get("type", {}).get("basic_group_id") == bg_id:
                    if chat_id in self._owned_chats:
                        del self._owned_chats[chat_id]
                        removed = True
                        logger.info("🗑️ Removed deleted/left group from owned list: ID %d", chat_id)
            if removed:
                self._sync_and_emit()
            return

        for chat_id, chat in self._raw_chats.items():
            if chat.get("type", {}).get("basic_group_id") == bg_id:
                self._evaluate_chat_ownership(chat_id)

    def process_chat_title_update(self, chat_id: int, new_title: str) -> None:
        if chat_id in self._raw_chats:
            self._raw_chats[chat_id]["title"] = new_title

        if chat_id in self._owned_chats:
            if is_music_title(new_title):
                old = self._owned_chats[chat_id]
                self._owned_chats[chat_id] = OwnedChat(
                    id=old.id,
                    title=new_title,
                    is_channel=old.is_channel,
                    supergroup_id=old.supergroup_id,
                    unread_count=old.unread_count,
                )
            else:
                del self._owned_chats[chat_id]
            self._sync_and_emit()
        else:
            self._evaluate_chat_ownership(chat_id)

    def _evaluate_chat_ownership(self, chat_id: int) -> None:
        chat = self._raw_chats.get(chat_id)
        if not chat:
            return

        title = chat.get("title", "")
        if not is_music_title(title):
            return

        chat_type = chat.get("type", {})
        type_str = chat_type.get("@type", "")

        if type_str == "chatTypeSupergroup":
            sg_id = chat_type.get("supergroup_id", 0)
            if sg_id in self._supergroups:
                sg = self._supergroups[sg_id]
                status = sg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or sg.get("is_creator", False):
                    self._add_owned_chat(
                        chat_id=chat_id,
                        title=title,
                        is_channel=sg.get("is_channel", True),
                        supergroup_id=sg_id,
                        unread_count=chat.get("unread_count", 0),
                    )
            else:
                self._adapter.send({
                    "@type": "getSupergroup",
                    "supergroup_id": sg_id,
                    "@extra": f"check_supergroup_{chat_id}",
                })

        elif type_str == "chatTypeBasicGroup":
            bg_id = chat_type.get("basic_group_id", 0)
            if bg_id in self._basic_groups:
                bg = self._basic_groups[bg_id]
                status = bg.get("status", {}).get("@type", "")
                if status == "chatMemberStatusCreator" or bg.get("is_creator", False):
                    self._add_owned_chat(
                        chat_id=chat_id,
                        title=title,
                        is_channel=False,
                        supergroup_id=0,
                        unread_count=chat.get("unread_count", 0),
                    )

    def _add_owned_chat(
        self, chat_id: int, title: str, is_channel: bool, supergroup_id: int, unread_count: int
    ) -> None:
        if chat_id in self._owned_chats:
            return

        if not is_music_title(title):
            return

        owned_chat = OwnedChat(
            id=chat_id,
            title=title,
            is_channel=is_channel,
            supergroup_id=supergroup_id,
            unread_count=unread_count,
        )
        self._owned_chats[chat_id] = owned_chat
        logger.info("Found owned music chat: %s (ID: %d)", title, chat_id)
        self._sync_and_emit()

    def _sync_and_emit(self) -> None:
        chat_list = list(self._owned_chats.values())
        if self._settings:
            self._settings.set_cached_music_chats(chat_list)
        self._on_owned_chats_updated(chat_list)

    def get_all_owned_chats(self) -> list[OwnedChat]:
        return list(self._owned_chats.values())