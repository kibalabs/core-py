from collections.abc import Iterator
from collections.abc import Sequence
from typing import TypeVar

ListItemType = TypeVar('ListItemType')


def generate_chunks(lst: Sequence[ListItemType], chunkSize: int) -> Iterator[Sequence[ListItemType]]:
    for index in range(0, len(lst), chunkSize):
        yield lst[index : index + chunkSize]
