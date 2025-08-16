from typing import Dict, List, Optional
import random

from .search_links import (
    DATABRICKS_TIER_1_BUSINESS,
    DATABRICKS_TIER_1_TRADE,
    AI_SEARCH_LINKS,
    CYBER_SECURITY_SEARCH_LINKS,
)


class PublicationQueue:
    """In-memory queue of publications built from curated search links.

    Produces deterministic objects with name, url, topics.
    """

    def __init__(self) -> None:
        self._publications: List[Dict[str, object]] = []
        self._current_index: int = 0
        self._initialize_publications()

    def _initialize_publications(self) -> None:
        all_links: Dict[str, str] = {}
        all_links.update(DATABRICKS_TIER_1_BUSINESS)
        all_links.update(DATABRICKS_TIER_1_TRADE)
        all_links.update(AI_SEARCH_LINKS)
        all_links.update(CYBER_SECURITY_SEARCH_LINKS)

        for name, url in all_links.items():
            publication = {
                "name": name,
                "url": url,
                "topics": self._topics_for(name),
            }
            self._publications.append(publication)

        random.shuffle(self._publications)

    def _topics_for(self, name: str) -> List[str]:
        topics: List[str] = []
        if name in DATABRICKS_TIER_1_BUSINESS or name in DATABRICKS_TIER_1_TRADE:
            topics.append("databricks")
        if name in AI_SEARCH_LINKS:
            topics.append("ai")
        if name in CYBER_SECURITY_SEARCH_LINKS:
            topics.append("cyber")
        return topics

    def next(self) -> Optional[Dict[str, object]]:
        if not self._publications:
            return None
        pub = self._publications[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._publications)
        return pub

    def current(self) -> Optional[Dict[str, object]]:
        if not self._publications:
            return None
        return self._publications[self._current_index]


queue_singleton = PublicationQueue()


