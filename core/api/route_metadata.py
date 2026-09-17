from __future__ import annotations

import typing

from pydantic import BaseModel


class RateLimitConfig(typing.TypedDict, total=False):
    perMinute: int
    perFiveMinutes: int
    perHour: int
    perDay: int


OpenApiSecurity = list[dict[str, list[str]]]


class SecurityScheme(typing.NamedTuple):
    name: str
    definition: dict[str, object]


class RouteMetadata(typing.TypedDict, total=False):
    requestType: type[BaseModel]
    responseType: type[BaseModel]
    streamed: bool
    operationId: str | None
    summary: str | None
    description: str | None
    tags: list[str]
    security: OpenApiSecurity
    rateLimit: RateLimitConfig
    extensions: dict[str, object]


def get_route_metadata(func: object) -> RouteMetadata:
    metadata = getattr(func, 'openapi', None)
    if not isinstance(metadata, dict):
        return {}
    return typing.cast(RouteMetadata, metadata)


def update_route_metadata(func: object, metadata: RouteMetadata) -> None:
    functionDict = getattr(func, '__dict__', None)
    if not isinstance(functionDict, dict):
        raise TypeError('Route metadata can only be attached to objects with a __dict__')
    existingMetadata = get_route_metadata(func)
    mergedMetadata: dict[str, object] = {**existingMetadata, **metadata}
    if 'extensions' in existingMetadata and 'extensions' in metadata:
        mergedMetadata['extensions'] = {**existingMetadata['extensions'], **metadata['extensions']}
    functionDict['openapi'] = mergedMetadata
