from __future__ import annotations

import re
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Protocol
from typing import cast

from pydantic import BaseModel
from starlette.requests import Request
from starlette.routing import BaseRoute
from starlette.schemas import EndpointInfo
from starlette.schemas import SchemaGenerator

from core.api.api_response import KibaJSONResponse
from core.api.route_metadata import OpenApiSecurityScheme
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import get_route_metadata

_PATH_PARAMETER_PATTERN = re.compile(r'{([A-Za-z0-9_]+)(?::[^}]+)?}')
_RATE_LIMIT_WINDOW_LABELS: dict[str, str] = {
    'perMinute': 'minute',
    'perFiveMinutes': '5 minutes',
    'perHour': 'hour',
    'perDay': 'day',
}


class OpenApiTag(BaseModel):
    name: str
    description: str | None = None


class OpenApiExtension(Protocol):
    def update_document(self, document: dict[str, object]) -> None: ...

    def update_operation(self, *, route: EndpointInfo, metadata: RouteMetadata, operation: dict[str, object]) -> None: ...


def _format_rate_limit_text(rateLimit: Mapping[str, int]) -> str:
    parts = [f'{rateLimit[key]} requests/{label}' for key, label in _RATE_LIMIT_WINDOW_LABELS.items() if key in rateLimit]
    return f'Rate limited to {", ".join(parts)}.'


def _schema_reference(model: type[BaseModel], schemas: dict[str, object]) -> dict[str, str]:
    modelSchema = cast(dict[str, object], model.model_json_schema(by_alias=True, ref_template='#/components/schemas/{model}'))
    definitions = modelSchema.pop('$defs', {})
    schemas.update(cast(dict[str, object], definitions))
    schemas[model.__name__] = modelSchema
    return {'$ref': f'#/components/schemas/{model.__name__}'}


def _get_path_parameter_names(path: str) -> set[str]:
    return {match.group(1) for match in _PATH_PARAMETER_PATTERN.finditer(path)}


def _get_request_schema(model: type[BaseModel]) -> dict[str, object]:
    return cast(dict[str, object], model.model_json_schema(by_alias=True))


def _get_path_parameters(model: type[BaseModel], path: str) -> list[dict[str, object]]:
    modelSchema = _get_request_schema(model=model)
    properties = cast(dict[str, dict[str, object]], modelSchema.get('properties', {}))
    pathParameterNames = _get_path_parameter_names(path)
    return [
        {
            'name': name,
            'in': 'path',
            'required': True,
            'schema': properties[name],
        }
        for name in properties
        if name in pathParameterNames
    ]


def _get_query_parameters(model: type[BaseModel], path: str) -> list[dict[str, object]]:
    modelSchema = _get_request_schema(model=model)
    properties = cast(dict[str, dict[str, object]], modelSchema.get('properties', {}))
    required = set(cast(list[str], modelSchema.get('required', [])))
    pathParameterNames = _get_path_parameter_names(path)
    return [
        {
            'name': name,
            'in': 'query',
            'required': name in required,
            'schema': propertySchema,
        }
        for name, propertySchema in properties.items()
        if name not in pathParameterNames
    ]


def _get_request_body_schema(model: type[BaseModel], path: str, schemas: dict[str, object]) -> dict[str, object]:
    modelSchema = cast(dict[str, object], model.model_json_schema(by_alias=True, ref_template='#/components/schemas/{model}'))
    definitions = modelSchema.pop('$defs', {})
    schemas.update(cast(dict[str, object], definitions))
    properties = cast(dict[str, dict[str, object]], modelSchema.get('properties', {}))
    pathParameterNames = _get_path_parameter_names(path)
    modelSchema['properties'] = {name: schema for name, schema in properties.items() if name not in pathParameterNames}
    required = cast(list[str], modelSchema.get('required', []))
    modelSchema['required'] = [name for name in required if name not in pathParameterNames]
    return modelSchema


class OpenApiSchemaGenerator(SchemaGenerator):
    def __init__(
        self,
        title: str,
        version: str,
        description: str,
        tags: Sequence[OpenApiTag],
        securitySchemes: Sequence[OpenApiSecurityScheme],
        extensions: Sequence[OpenApiExtension] = (),
    ) -> None:
        super().__init__({'openapi': '3.0.3', 'info': {'title': title, 'version': version}})
        self.title = title
        self.version = version
        self.description = description
        self.tags = tags
        self.securitySchemes = {scheme.name: scheme.definition for scheme in securitySchemes}
        self.tagOrder = {tag.name: index for index, tag in enumerate(tags)}
        self.extensions = extensions

    def get_schema(self, routes: list[BaseRoute]) -> dict[str, object]:
        document: dict[str, object] = {
            'openapi': '3.0.3',
            'info': {
                'title': self.title,
                'version': self.version,
                'description': self.description,
            },
            'tags': [tag.model_dump(exclude_none=True) for tag in self.tags],
            'paths': {},
            'components': {
                'schemas': {},
                'securitySchemes': self.securitySchemes,
            },
        }
        paths = cast(dict[str, object], document['paths'])
        components = cast(dict[str, object], document['components'])
        schemas = cast(dict[str, object], components['schemas'])

        def sort_key(endpoint: object) -> int:
            metadata = get_route_metadata(getattr(endpoint, 'func', None))
            if metadata.get('operationId') is None:
                return len(self.tagOrder)
            endpointTags = metadata.get('tags', [])
            tag = endpointTags[0] if endpointTags else ''
            return self.tagOrder.get(tag, len(self.tagOrder))

        for endpoint in sorted(self.get_endpoints(routes), key=sort_key):
            metadata = get_route_metadata(endpoint.func)
            if metadata.get('operationId') is None:
                continue
            requestType = metadata['requestType']
            responseType = metadata['responseType']
            operation: dict[str, object] = {
                'operationId': metadata['operationId'],
                'summary': metadata['summary'],
                'tags': metadata['tags'],
                'responses': {
                    '200': {
                        'description': 'Successful response',
                        'content': {
                            'application/x-ndjson' if metadata['streamed'] else 'application/json': {
                                'schema': _schema_reference(model=responseType, schemas=schemas),
                            },
                        },
                    },
                },
            }
            if metadata['description'] is not None:
                operation['description'] = metadata['description']
            rateLimit = metadata.get('rateLimit')
            if rateLimit:
                rateLimitText = _format_rate_limit_text(rateLimit=cast(Mapping[str, int], rateLimit))
                existingDescription = cast(str, operation.get('description', ''))
                operation['description'] = f'{existingDescription}\n\n{rateLimitText}'.strip()
            security = metadata.get('security')
            if security is not None:
                operation['security'] = security
            if endpoint.http_method in {'get', 'delete'}:
                parameters = _get_path_parameters(model=requestType, path=endpoint.path) + _get_query_parameters(model=requestType, path=endpoint.path)
                if parameters:
                    operation['parameters'] = parameters
            else:
                pathParameters = _get_path_parameters(model=requestType, path=endpoint.path)
                if pathParameters:
                    operation['parameters'] = pathParameters
                bodySchema = _get_request_body_schema(model=requestType, path=endpoint.path, schemas=schemas)
                if bodySchema.get('properties'):
                    operation['requestBody'] = {
                        'required': bool(bodySchema.get('required')),
                        'content': {
                            'application/json': {
                                'schema': bodySchema,
                            },
                        },
                    }
            for extension in self.extensions:
                extension.update_operation(route=endpoint, metadata=metadata, operation=operation)
            pathOperations = cast(dict[str, object], paths.setdefault(endpoint.path, {}))
            pathOperations[endpoint.http_method] = operation
        for extension in self.extensions:
            extension.update_document(document=document)
        return document


def create_openapi_response(schemaGenerator: OpenApiSchemaGenerator) -> Callable[[Request], KibaJSONResponse]:
    def get_openapi_response(request: Request) -> KibaJSONResponse:
        return KibaJSONResponse(content=schemaGenerator.get_schema(routes=request.app.routes))

    return get_openapi_response
