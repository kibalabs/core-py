from collections.abc import Iterator
from collections.abc import Sequence
from typing import TypeVar

ListItemType = TypeVar('ListItemType')


def generate_chunks(lst: Sequence[ListItemType], chunkSize: int) -> Iterator[Sequence[ListItemType]]:
    for index in range(0, len(lst), chunkSize):
        yield lst[index : index + chunkSize]


def remove_nones(lst: Sequence[ListItemType | None]) -> list[ListItemType]:
    return [item for item in lst if item is not None]
