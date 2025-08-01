from __future__ import annotations

from collections.abc import Mapping

from core.util.typing_util import JsonObject


class KibaException(Exception):  # noqa: N818
    def __init__(self, message: str | None, statusCode: int | None = None, exceptionType: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.statusCode = statusCode or 500
        self.exceptionType = exceptionType if exceptionType else self.__class__.__name__

    @staticmethod
    def from_exception(exception: Exception, statusCode: int = 500) -> KibaException:
        if isinstance(exception, KibaException):
            return exception
        return KibaException(message=str(exception), statusCode=statusCode, exceptionType=exception.__class__.__name__)

    def to_dict(self) -> JsonObject:
        return {
            'exceptionType': self.exceptionType,
            'message': self.message,
            'fields': {},
            'statusCode': self.statusCode,
        }

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(statusCode={self.statusCode!r}, exceptionType={self.exceptionType!r}, message={self.message!r})'

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, KibaException) and self.statusCode == other.statusCode and self.exceptionType == other.exceptionType

    def __hash__(self) -> int:
        return hash((self.statusCode, self.exceptionType))


class ClientException(KibaException):
    pass


class BadRequestException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Bad Request'
        super().__init__(message=message, statusCode=400)


class UnauthorizedException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Unauthorized'
        super().__init__(message=message, statusCode=401)


class PaymentRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Payment Required'
        super().__init__(message=message, statusCode=402)


class ForbiddenException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Forbidden'
        super().__init__(message=message, statusCode=403)


class NotFoundException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Not Found'
        super().__init__(message=message, statusCode=404)


class MethodNotAllowedException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Method Not Allowed'
        super().__init__(message=message, statusCode=405)


class NotAcceptableException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Not Acceptable'
        super().__init__(message=message, statusCode=406)


class ProxyAuthenticationRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Proxy Authentication Required'
        super().__init__(message=message, statusCode=407)


class RequestTimeoutException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Request Timeout'
        super().__init__(message=message, statusCode=408)


class ConflictException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Conflict'
        super().__init__(message=message, statusCode=409)


class GoneException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Gone'
        super().__init__(message=message, statusCode=410)


class LengthRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Length Required'
        super().__init__(message=message, statusCode=411)


class PreconditionFailedException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Precondition Failed'
        super().__init__(message=message, statusCode=412)


class PayloadTooLargeException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Payload Too Large'
        super().__init__(message=message, statusCode=413)


class UriTooLongException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'URI Too Long'
        super().__init__(message=message, statusCode=414)


class UnsupportedMediaTypeException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Unsupported Media Type'
        super().__init__(message=message, statusCode=415)


class RangeNotSatisfiableException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Range Not Satisfiable'
        super().__init__(message=message, statusCode=416)


class ExpectationFailedException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Expectation Failed'
        super().__init__(message=message, statusCode=417)


class ImATeapotException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else "I'm a teapot"
        super().__init__(message=message, statusCode=418)


class MisdirectedRequestException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Misdirected Request'
        super().__init__(message=message, statusCode=421)


class UnprocessableEntityException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Unprocessable Entity'
        super().__init__(message=message, statusCode=422)


class LockedException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Locked'
        super().__init__(message=message, statusCode=423)


class FailedDependencyException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Failed Dependency'
        super().__init__(message=message, statusCode=424)


class UpgradeRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Upgrade Required'
        super().__init__(message=message, statusCode=426)


class PreconditionRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Precondition Required'
        super().__init__(message=message, statusCode=428)


class TooManyRequestsException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Too Many Requests'
        super().__init__(message=message, statusCode=429)


class RequestHeaderFieldsTooLargeException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Request Header Fields Too Large'
        super().__init__(message=message, statusCode=431)


class UnavailableForLegalReasonsException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Unavailable For Legal Reasons'
        super().__init__(message=message, statusCode=451)


class NoResponseException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'No Response'
        super().__init__(message=message, statusCode=444)


class RequestHeaderTooLargeException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Request Header Too Large'
        super().__init__(message=message, statusCode=494)


class SSLCertificateErrorException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'SSL Certificate Error'
        super().__init__(message=message, statusCode=495)


class SSLCertificateRequiredException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'SSL Certificate Required'
        super().__init__(message=message, statusCode=496)


class HttpRequestSentToHttpsException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'HTTP Request Sent to HTTPS Port'
        super().__init__(message=message, statusCode=497)


class ClientClosedRequestException(ClientException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Client Closed Request'
        super().__init__(message=message, statusCode=499)


class ServerException(KibaException):
    pass


class InternalServerErrorException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Internal Server Error'
        super().__init__(message=message, statusCode=500)


class NotImplementedException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Not Implemented'
        super().__init__(message=message, statusCode=501)


class BadGatewayException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Bad Gateway'
        super().__init__(message=message, statusCode=502)


class ServiceUnavailableException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Service Unavailable'
        super().__init__(message=message, statusCode=503)


class GatewayTimeoutException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Gateway Timeout'
        super().__init__(message=message, statusCode=504)


class HttpVersionNotSupportedException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'HTTP Version Not Supported'
        super().__init__(message=message, statusCode=505)


class VariantAlsoNegotiatesException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Variant Also Negotiates'
        super().__init__(message=message, statusCode=506)


class InsufficientStorageException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Insufficient Storage'
        super().__init__(message=message, statusCode=507)


class LoopDetectedException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Loop Detected'
        super().__init__(message=message, statusCode=508)


class BandwidthLimitExceededException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Bandwidth Limit Exceeded'
        super().__init__(message=message, statusCode=509)


class NotExtendedException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Not Extended'
        super().__init__(message=message, statusCode=510)


class NetworkAuthenticationRequiredException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Network Authentication Required'
        super().__init__(message=message, statusCode=511)


class UnknownErrorException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Unknown Error'
        super().__init__(message=message, statusCode=520)


class WebServerIsDownException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Web Server Is Down'
        super().__init__(message=message, statusCode=521)


class ConnectionTimeoutException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Connection Timeout'
        super().__init__(message=message, statusCode=522)


class UnreachableOriginException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Origin Is Unreachable'
        super().__init__(message=message, statusCode=523)


class TimeoutOccurredException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'A Timeout Occurred'
        super().__init__(message=message, statusCode=524)


class SSLHandshakeFailedException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'SSL Handshake Failed'
        super().__init__(message=message, statusCode=525)


class InvalidSSLCertificateException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Invalid SSL Certificate'
        super().__init__(message=message, statusCode=526)


class RailgunErrorException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Railgun Error'
        super().__init__(message=message, statusCode=527)


class OriginDNSErrorException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Origin DNS Error'
        super().__init__(message=message, statusCode=530)


class NetworkReadTimeoutException(ServerException):
    def __init__(self, message: str | None = None) -> None:
        message = message if message else 'Network Read Timeout'
        super().__init__(message=message, statusCode=598)


class DuplicateValueException(BadRequestException):
    pass


class RedirectException(KibaException):
    def __init__(self, location: str, statusCode: int, message: str | None = None, shouldAddCacheHeader: bool | None = True) -> None:
        message = message if message else 'RedirectException'
        super().__init__(message=message, statusCode=statusCode)
        self.location = location
        self.shouldAddCacheHeader = shouldAddCacheHeader


class MovedPermanentlyRedirectException(RedirectException):
    def __init__(self, location: str, message: str | None = None, shouldAddCacheHeader: bool | None = True) -> None:
        message = message if message else 'Moved Permanently'
        super().__init__(location=location, message=message, statusCode=301, shouldAddCacheHeader=shouldAddCacheHeader)


class FoundRedirectException(RedirectException):
    def __init__(self, location: str, message: str | None = None) -> None:
        message = message if message else 'Found Redirect'
        super().__init__(location=location, message=message, statusCode=302, shouldAddCacheHeader=False)


class PermanentRedirectException(RedirectException):
    def __init__(self, location: str, message: str | None = None, shouldAddCacheHeader: bool | None = True) -> None:
        message = message if message else 'Permanent Redirect'
        super().__init__(location=location, message=message, statusCode=308, shouldAddCacheHeader=shouldAddCacheHeader)


CLIENT_EXCEPTIONS_MAP = {
    400: BadRequestException,
    401: UnauthorizedException,
    402: PaymentRequiredException,
    403: ForbiddenException,
    404: NotFoundException,
    405: MethodNotAllowedException,
    406: NotAcceptableException,
    407: ProxyAuthenticationRequiredException,
    408: RequestTimeoutException,
    409: ConflictException,
    410: GoneException,
    411: LengthRequiredException,
    412: PreconditionFailedException,
    413: PayloadTooLargeException,
    414: UriTooLongException,
    415: UnsupportedMediaTypeException,
    416: RangeNotSatisfiableException,
    417: ExpectationFailedException,
    418: ImATeapotException,
    421: MisdirectedRequestException,
    422: UnprocessableEntityException,
    423: LockedException,
    424: FailedDependencyException,
    426: UpgradeRequiredException,
    428: PreconditionRequiredException,
    429: TooManyRequestsException,
    431: RequestHeaderFieldsTooLargeException,
    444: NoResponseException,
    451: UnavailableForLegalReasonsException,
    494: RequestHeaderTooLargeException,
    495: SSLCertificateErrorException,
    496: SSLCertificateRequiredException,
    497: HttpRequestSentToHttpsException,
    499: ClientClosedRequestException,
}

SERVER_EXCEPTIONS_MAP = {
    500: InternalServerErrorException,
    501: NotImplementedException,
    502: BadGatewayException,
    503: ServiceUnavailableException,
    504: GatewayTimeoutException,
    505: HttpVersionNotSupportedException,
    506: VariantAlsoNegotiatesException,
    507: InsufficientStorageException,
    508: LoopDetectedException,
    509: BandwidthLimitExceededException,
    510: NotExtendedException,
    511: NetworkAuthenticationRequiredException,
    520: UnknownErrorException,
    521: WebServerIsDownException,
    522: ConnectionTimeoutException,
    523: UnreachableOriginException,
    524: TimeoutOccurredException,
    525: SSLHandshakeFailedException,
    526: InvalidSSLCertificateException,
    527: RailgunErrorException,
    530: OriginDNSErrorException,
    598: NetworkReadTimeoutException,
}

HTTP_EXCEPTIONS_MAP: Mapping[int, type[ServerException | ClientException]] = {**SERVER_EXCEPTIONS_MAP, **CLIENT_EXCEPTIONS_MAP}

CLIENT_EXCEPTIONS = list(CLIENT_EXCEPTIONS_MAP.values())
SERVER_EXCEPTIONS = list(SERVER_EXCEPTIONS_MAP.values())
HTTP_EXCEPTIONS = CLIENT_EXCEPTIONS + SERVER_EXCEPTIONS
