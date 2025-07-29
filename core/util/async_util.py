import asyncio
import typing

AwaitableReturnType = typing.TypeVarTuple('AwaitableReturnType')


# NOTE(krishan711): apparently mypy has a special case for asyncio.gather so we can't replicate it exactly
# Instead, we have a function that can only return a list of the same type, i think this is better for large
# lists anyway!
async def gather_batched[AwaitableReturnType](
    *awaitables: typing.Awaitable[AwaitableReturnType],
    batchSize: int,
) -> list[AwaitableReturnType]:
    results: list[AwaitableReturnType] = []
    for i in range(0, len(awaitables), batchSize):
        batch = awaitables[i : i + batchSize]
        results.extend(await asyncio.gather(*batch, return_exceptions=False))
    return results


# NOTE(krishan711): not sure how to do the typing for this one
# async def gather_batched_with_exceptions[AwaitableType](
#     *awaitables: typing.Unpack[typing.Awaitable[AwaitableType]],
#     batchSize: int,
# ) -> tuple[typing.Unpack[AwaitableType]]:
#     results = []
#     for i in range(0, len(awaitables), batchSize):
#         batch = awaitables[i : i + batchSize]
#         results.extend(await asyncio.gather(*batch, return_exceptions=True))
#     return tuple(results)
