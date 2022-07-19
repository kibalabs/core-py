from typing import Iterator
from typing import List
from typing import TypeVar

ListItemType = TypeVar('ListItemType')  # pylint: disable=invalid-name

def generate_chunks(lst: List[ListItemType], chunkSize: int) -> Iterator[List[ListItemType]]:
    for index in range(0, len(lst), chunkSize):
        yield lst[index: index + chunkSize]
