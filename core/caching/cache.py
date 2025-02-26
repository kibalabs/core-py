from abc import ABC
from abc import abstractmethod


class Cache(ABC):
    def __init__(self, isPrivate: bool = False) -> None:
        super().__init__()
        self.isPrivate = isPrivate

    @abstractmethod
    async def set(self, key: str, value: str, expirySeconds: float) -> bool: ...

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Returned bool indicates whether the record was removed or not
        """
        ...

    @abstractmethod
    def can_store_complex_objects(self) -> bool: ...
