from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseConnector(ABC):
    platform_name: str

    @abstractmethod
    def get_auth_url(self) -> str:
        """Returns OAuth URL for the UI to redirect to."""

    @abstractmethod
    def handle_oauth_callback(self, code: str) -> dict:
        """Exchanges auth code for tokens and saves to DB."""

    @abstractmethod
    def poll(self, campaign_config: dict) -> List[Dict[str, Any]]:
        """Polls platform for new data. Returns list of raw records."""

    @abstractmethod
    def normalize(self, raw: dict, data_type: str) -> dict:
        """Converts platform payload to standard shape for landing zone."""

    @abstractmethod
    def make_dedup_key(self, record: dict) -> str:
        """Returns SHA-256 hash string used as dedup identifier."""
