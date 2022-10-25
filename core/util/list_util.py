from typing import Iterator, Sequence
from typing import List
from typing import TypeVar

ListItemType = TypeVar('ListItemType')  # pylint: disable=invalid-name

def generate_chunks(lst: Sequence[ListItemType], chunkSize: int) -> Iterator[Sequence[ListItemType]]:
    for index in range(0, len(lst), chunkSize):
        yield lst[index: index + chunkSize]
