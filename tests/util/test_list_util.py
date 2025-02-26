from core.util import list_util


class TestListUtil:

    def test_generate_chunks_with_even_division(self):
        inputList = [1, 2, 3, 4, 5, 6]
        chunkSize = 2
        expected = [[1, 2], [3, 4], [5, 6]]
        result = list(list_util.generate_chunks(inputList, chunkSize))
        assert result == expected

    def test_generate_chunks_with_uneven_division(self):
        inputList = [1, 2, 3, 4, 5]
        chunkSize = 2
        expected = [[1, 2], [3, 4], [5]]
        result = list(list_util.generate_chunks(inputList, chunkSize))
        assert result == expected

    def test_generate_chunks_with_empty_list(self):
        inputList: list[int] = []
        chunkSize = 2
        expected = []
        result = list(list_util.generate_chunks(inputList, chunkSize))
        assert result == expected

    def test_generate_chunks_with_chunk_size_larger_than_list(self):
        inputList = [1, 2, 3]
        chunkSize = 5
        expected = [[1, 2, 3]]
        result = list(list_util.generate_chunks(inputList, chunkSize))
        assert result == expected

    def test_generate_chunks_with_different_types(self):
        inputList = ["a", "b", "c", "d"]
        chunkSize = 3
        expected = [["a", "b", "c"], ["d"]]
        result = list(list_util.generate_chunks(inputList, chunkSize))
        assert result == expected
