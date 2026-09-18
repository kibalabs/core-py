from pydantic import BaseModel
from starlette.routing import Route
from starlette.schemas import EndpointInfo

from core.api.api_request import KibaApiRequest
from core.api.json_route import json_route
from core.api.route import create_route
from core.api.route_auth import RouteAuthResolver
from core.api.openapi import OpenApiExtension
from core.api.openapi import OpenApiSchemaGenerator
from core.api.openapi import OpenApiTag
from core.api.route_metadata import RouteMetadata
from core.api.route_metadata import SecurityScheme


class PublicRouteAuthResolver(RouteAuthResolver):
    async def authorize_route(self, *, auth: str, request: KibaApiRequest[BaseModel]) -> None:
        raise ValueError(f'Unknown auth policy: {auth}')

    def get_route_security_schemes(self, *, auth: str) -> list[str]:
        raise ValueError(f'Unknown auth policy: {auth}')


route = create_route(authResolver=PublicRouteAuthResolver())


class ExampleRequest(BaseModel):
    itemId: str
    value: str


class ExampleResponse(BaseModel):
    result: str


class ExampleExtension(OpenApiExtension):
    def update_document(self, document: dict[str, object]) -> None:
        document['x-example-document'] = True

    def update_operation(self, *, route: EndpointInfo, metadata: RouteMetadata, operation: dict[str, object]) -> None:
        operation['x-example-route'] = route.path
        operation['x-example-metadata'] = metadata['extensions']


def test_openapi_generator_builds_routes_and_runs_extensions() -> None:
    @route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='getExample',
        summary='Get an example',
        description='An example endpoint.',
        tags=['Examples'],
        rateLimit={'perMinute': 3, 'perHour': 30},
        extensions={'exampleSetting': 'enabled'},
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[OpenApiTag(name='Examples', description='Example operations.')],
        securitySchemes=[SecurityScheme(name='ExampleApiKey', definition={'type': 'apiKey', 'in': 'header', 'name': 'X-Example-Key'})],
        extensions=(ExampleExtension(),),
    )

    schema = generator.get_schema(routes=[Route('/examples/{itemId}', endpoint, methods=['POST'])])
    operation = schema['paths']['/examples/{itemId}']['post']

    assert operation['operationId'] == 'getExample'
    assert operation['summary'] == 'Get an example'
    assert 'An example endpoint.' in operation['description']
    assert '3 requests/minute' in operation['description']
    assert '30 requests/hour' in operation['description']
    assert operation['x-example-route'] == '/examples/{itemId}'
    assert operation['x-example-metadata'] == {'exampleSetting': 'enabled'}
    assert schema['x-example-document'] is True
    assert schema['components']['securitySchemes']['ExampleApiKey']['name'] == 'X-Example-Key'
    assert schema['tags'] == [{'name': 'Examples', 'description': 'Example operations.'}]


def test_openapi_generator_omits_tag_description_when_unset() -> None:
    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[OpenApiTag(name='Examples')],
        securitySchemes=[],
    )

    schema = generator.get_schema(routes=[])
    assert schema['tags'] == [{'name': 'Examples'}]


    @route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='streamExample',
        tags=['Examples'],
        isStreaming=True,
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]):
        yield ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[OpenApiTag(name='Examples')],
        securitySchemes=[],
    )

    schema = generator.get_schema(routes=[Route('/examples/stream', endpoint, methods=['POST'])])
    operation = schema['paths']['/examples/stream']['post']

    assert 'application/x-ndjson' in operation['responses']['200']['content']


def test_json_route_is_not_documented() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    async def undocumented_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[],
        securitySchemes=[],
    )

    schema = generator.get_schema(routes=[Route('/undocumented', undocumented_endpoint, methods=['POST'])])
    assert schema['paths'] == {}


def test_openapi_generator_orders_operations_by_declared_tag_position() -> None:
    @route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='second', tags=['Second'])
    async def second_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    @route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='first', tags=['First'])
    async def first_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[OpenApiTag(name='First'), OpenApiTag(name='Second')],
        securitySchemes=[],
    )

    schema = generator.get_schema(routes=[Route('/second', second_endpoint, methods=['POST']), Route('/first', first_endpoint, methods=['POST'])])
    orderedOperationIds = [operation.get('operationId') for path in schema['paths'].values() for operation in path.values()]
    assert orderedOperationIds == ['first', 'second']



def test_authorize_signature_auto_documents_security_scheme() -> None:
    exampleSignatureScheme = SecurityScheme(name='ExampleSignature', definition={'type': 'apiKey', 'in': 'header', 'name': 'Authorization'})

    class SignatureRouteAuthResolver(RouteAuthResolver):
        async def authorize_route(self, *, auth: str, request: KibaApiRequest[BaseModel]) -> None:
            raise ValueError(f'Unknown auth policy: {auth}')

        def get_route_security_schemes(self, *, auth: str) -> list[str]:
            if auth == 'signature':
                return [exampleSignatureScheme.name]
            raise ValueError(f'Unknown auth policy: {auth}')

    route = create_route(authResolver=SignatureRouteAuthResolver())

    @route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='secureExample',
        tags=['Examples'],
        auth='signature',
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[OpenApiTag(name='Examples')],
        securitySchemes=[exampleSignatureScheme],
    )

    schema = generator.get_schema(routes=[Route('/secure', endpoint, methods=['POST'])])
    operation = schema['paths']['/secure']['post']
    assert operation['security'] == [{'ExampleSignature': []}]
    assert schema['components']['securitySchemes']['ExampleSignature']['name'] == 'Authorization'
