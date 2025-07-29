import asyncio
import pytest

from core.util import async_util


class TestAsyncUtil:

    @pytest.mark.asyncio
    async def test_gather_batched_with_small_batch(self):
        async def async_identity(value: int) -> int:
            await asyncio.sleep(0.01)  # Small delay to simulate async work
            return value
        awaitables = [async_identity(i) for i in range(5)]
        result = await async_util.gather_batched(*awaitables, batchSize=2)
        assert result == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_gather_batched_with_large_batch(self):
        async def async_double(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 2
        awaitables = [async_double(i) for i in range(10)]
        result = await async_util.gather_batched(*awaitables, batchSize=5)
        assert result == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    @pytest.mark.asyncio
    async def test_gather_batched_with_batch_size_larger_than_awaitables(self):
        async def async_square(value: int) -> int:
            await asyncio.sleep(0.01)
            return value ** 2
        awaitables = [async_square(i) for i in range(3)]
        result = await async_util.gather_batched(*awaitables, batchSize=10)
        assert result == [0, 1, 4]

    @pytest.mark.asyncio
    async def test_gather_batched_with_batch_size_one(self):
        async def async_increment(value: int) -> int:
            await asyncio.sleep(0.01)
            return value + 1
        awaitables = [async_increment(i) for i in range(4)]
        result = await async_util.gather_batched(*awaitables, batchSize=1)
        assert result == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_gather_batched_with_empty_awaitables(self):
        result = await async_util.gather_batched(batchSize=2)
        assert result == []

    @pytest.mark.asyncio
    async def test_gather_batched_with_single_awaitable(self):
        async def async_triple(value: int) -> int:
            await asyncio.sleep(0.01)
            return value * 3
        awaitable = async_triple(5)
        result = await async_util.gather_batched(awaitable, batchSize=1)
        assert result == [15]

    @pytest.mark.asyncio
    async def test_gather_batched_with_different_types(self):
        async def async_string(value: str) -> str:
            await asyncio.sleep(0.01)
            return f"processed_{value}"
        awaitables = [async_string(f"item{i}") for i in range(3)]
        result = await async_util.gather_batched(*awaitables, batchSize=2)
        assert result == ["processed_item0", "processed_item1", "processed_item2"]

    @pytest.mark.asyncio
    async def test_gather_batched_preserves_order(self):
        async def async_delayed_return(value: int, delay: float) -> int:
            await asyncio.sleep(delay)
            return value
        # Create awaitables with different delays to test ordering
        awaitables = [
            async_delayed_return(0, 0.03),
            async_delayed_return(1, 0.01),
            async_delayed_return(2, 0.02),
            async_delayed_return(3, 0.005),
        ]
        result = await async_util.gather_batched(*awaitables, batchSize=2)
        # Results should be in original order despite different completion times
        assert result == [0, 1, 2, 3]

    @pytest.mark.asyncio
    async def test_gather_batched_with_exception_propagation(self):
        async def async_with_exception(value: int) -> int:
            await asyncio.sleep(0.01)
            if value == 2:
                raise ValueError(f"Error for value {value}")
            return value
        awaitables = [async_with_exception(i) for i in range(4)]
        with pytest.raises(ValueError, match="Error for value 2"):
            await async_util.gather_batched(*awaitables, batchSize=2)

    @pytest.mark.asyncio
    async def test_gather_batched_performance_benefit(self):
        call_times = []
        async def async_track_time(value: int) -> int:
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Longer delay to see batching effect
            return value
        awaitables = [async_track_time(i) for i in range(6)]
        start_time = asyncio.get_event_loop().time()
        result = await async_util.gather_batched(*awaitables, batchSize=3)
        end_time = asyncio.get_event_loop().time()
        assert result == [0, 1, 2, 3, 4, 5]
        # With batch size 3 and 6 items, we should have 2 batches
        # Total time should be around 0.2 seconds (2 batches * 0.1 seconds each)
        # Allow some tolerance for test execution overhead
        assert 0.15 < (end_time - start_time) < 0.35
