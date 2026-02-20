from __future__ import annotations

from abc import ABC, abstractmethod


class TransportBase(ABC):
    @abstractmethod
    def send(self, payload: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def receive(self) -> list[dict]:
        raise NotImplementedError

    def receive_incremental(self, cursors: dict[str, int] | None = None) -> tuple[list[dict], dict[str, int]]:
        payloads = self.receive()
        return payloads, dict(cursors or {})

    def update_presence(self, presence: dict) -> None:
        _ = presence

    def receive_presence(self) -> list[dict]:
        return []
