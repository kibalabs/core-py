from pydantic import BaseModel
from starlette.routing import Route
from starlette.schemas import EndpointInfo

from core.api.api_request import KibaApiRequest
from core.api.authorizer import SignatureAuthorizer
from core.api.authorizer import authorize_signature
from core.api.json_route import json_route
from core.api.openapi import OpenApiExtension
from core.api.openapi import OpenApiSchemaGenerator
from core.api.route_metadata import RouteMetadata
from core.api.streaming_json_route import streaming_json_route


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
    @json_route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='getExample',
        summary='Get an example',
        description='An example endpoint.',
        tags=['Examples'],
        security=[{'ExampleApiKey': []}],
        rateLimit={'perMinute': 3, 'perHour': 30},
        extensions={'exampleSetting': 'enabled'},
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[{'name': 'Examples'}],
        securitySchemes={'ExampleApiKey': {'type': 'apiKey', 'in': 'header', 'name': 'X-Example-Key'}},
        extensions=(ExampleExtension(),),
    )

    schema = generator.get_schema(routes=[Route('/examples/{itemId}', endpoint, methods=['POST'])])
    operation = schema['paths']['/examples/{itemId}']['post']

    assert operation['operationId'] == 'getExample'
    assert operation['summary'] == 'Get an example'
    assert operation['security'] == [{'ExampleApiKey': []}]
    assert 'An example endpoint.' in operation['description']
    assert '3 requests/minute' in operation['description']
    assert '30 requests/hour' in operation['description']
    assert operation['x-example-route'] == '/examples/{itemId}'
    assert operation['x-example-metadata'] == {'exampleSetting': 'enabled'}
    assert schema['x-example-document'] is True
    assert schema['components']['securitySchemes']['ExampleApiKey']['name'] == 'X-Example-Key'


def test_openapi_generator_uses_stream_content_type() -> None:
    @streaming_json_route(
        requestType=ExampleRequest,
        responseType=ExampleResponse,
        operationId='streamExample',
        tags=['Examples'],
    )
    async def endpoint(request: KibaApiRequest[ExampleRequest]):
        yield ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[{'name': 'Examples'}],
        securitySchemes={},
    )

    schema = generator.get_schema(routes=[Route('/examples/stream', endpoint, methods=['POST'])])
    operation = schema['paths']['/examples/stream']['post']

    assert 'application/x-ndjson' in operation['responses']['200']['content']


def test_openapi_generator_skips_routes_without_operation_id() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse)
    async def undocumented_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[],
        securitySchemes={},
    )

    schema = generator.get_schema(routes=[Route('/undocumented', undocumented_endpoint, methods=['POST'])])
    assert schema['paths'] == {}


def test_openapi_generator_orders_operations_by_declared_tag_position() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='second', tags=['Second'])
    async def second_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    @json_route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='first', tags=['First'])
    async def first_endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[{'name': 'First'}, {'name': 'Second'}],
        securitySchemes={},
    )

    schema = generator.get_schema(routes=[Route('/second', second_endpoint, methods=['POST']), Route('/first', first_endpoint, methods=['POST'])])
    orderedOperationIds = [operation.get('operationId') for path in schema['paths'].values() for operation in path.values()]
    assert orderedOperationIds == ['first', 'second']


class ExampleSignatureAuthorizer(SignatureAuthorizer):
    async def retrieve_signature_signer(self, signatureString: str) -> str:
        return 'signer'


def test_authorize_signature_auto_documents_security_scheme() -> None:
    @json_route(requestType=ExampleRequest, responseType=ExampleResponse, operationId='secureExample', tags=['Examples'])
    @authorize_signature(authorizer=ExampleSignatureAuthorizer(), securitySchemeName='ExampleSignature')
    async def endpoint(request: KibaApiRequest[ExampleRequest]) -> ExampleResponse:
        return ExampleResponse(result=request.data.value)

    generator = OpenApiSchemaGenerator(
        title='Example API',
        version='1.0.0',
        description='Example API description.',
        tags=[{'name': 'Examples'}],
        securitySchemes={'ExampleSignature': {'type': 'apiKey', 'in': 'header', 'name': 'Authorization'}},
    )

    schema = generator.get_schema(routes=[Route('/secure', endpoint, methods=['POST'])])
    operation = schema['paths']['/secure']['post']
    assert operation['security'] == [{'ExampleSignature': []}]
