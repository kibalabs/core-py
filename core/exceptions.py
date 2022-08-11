from __future__ import annotations

from typing import Dict
from typing import Mapping
from typing import Optional
from typing import Type
from typing import Union

from core.util.typing_util import JSON


class KibaException(Exception):

    def __init__(self, message: Optional[str], statusCode: Optional[int] = None, exceptionType: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.statusCode = statusCode or 500
        self.exceptionType = exceptionType if exceptionType else self.__class__.__name__

    @staticmethod
    def from_exception(exception: Exception, statusCode: int = 500) -> KibaException:
        if isinstance(exception, KibaException):
            return exception
        return KibaException(message=str(exception), statusCode=statusCode, exceptionType=exception.__class__.__name__)

    def to_dict(self) -> Dict[str, JSON]:
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

    def __init__(self, message: Optional[str] = None) -> None:
        message = message if message else 'Bad Request'
        super().__init__(message=message, statusCode=400)


class UnauthorizedException(ClientException):

    def __init__(self, message: Optional[str] = None) -> None:
        message = message if message else 'Unauthorized'
        super().__init__(message=message, statusCode=401)


class ForbiddenException(ClientException):

    def __init__(self, message: Optional[str] = None) -> None:
        message = message if message else 'Forbidden'
        super().__init__(message=message, statusCode=403)


class NotFoundException(ClientException):

    def __init__(self, message: Optional[str] = None) -> None:
        message = message if message else 'Not Found'
        super().__init__(message=message, statusCode=404)


class ServerException(KibaException):
    pass


class InternalServerErrorException(ServerException):

    def __init__(self, message: Optional[str] = None) -> None:
        message = message if message else 'Internal Server Error'
        super().__init__(message=message, statusCode=500)

class DuplicateValueException(BadRequestException):
    pass


class RedirectException(KibaException):

    def __init__(self, location: str, statusCode: int, message: Optional[str] = None, shouldAddCacheHeader: Optional[bool] = True) -> None:
        message = message if message else 'RedirectException'
        super().__init__(message=message, statusCode=statusCode)
        self.location = location
        self.shouldAddCacheHeader = shouldAddCacheHeader


class MovedPermanentlyRedirectException(RedirectException):

    def __init__(self, location: str, message: Optional[str] = None, shouldAddCacheHeader: Optional[bool] = True) -> None:
        message = message if message else 'Moved Permanently'
        super().__init__(location=location, message=message, statusCode=301, shouldAddCacheHeader=shouldAddCacheHeader)


class FoundRedirectException(RedirectException):

    def __init__(self, location: str, message: Optional[str] = None) -> None:
        message = message if message else 'Found Redirect'
        super().__init__(location=location, message=message, statusCode=302, shouldAddCacheHeader=False)


class PermanentRedirectException(RedirectException):

    def __init__(self, location: str, message: Optional[str] = None, shouldAddCacheHeader: Optional[bool] = True) -> None:
        message = message if message else 'Permanent Redirect'
        super().__init__(location=location, message=message, statusCode=308, shouldAddCacheHeader=shouldAddCacheHeader)


CLIENT_EXCEPTIONS = [
    BadRequestException,
    ClientException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    # ConflictException,
    # ExpectationFailedException,
    # FailedDependencyException,
    # GoneException,
    # ImATeapotException,
    # LengthRequiredException,
    # LockedException,
    # MethodNotAllowedException,
    # MisdirectedRequestException,
    # NotAcceptableException,
    # PayloadTooLargeException,
    # PaymentRequiredException,
    # PreconditionFailedException,
    # PreconditionRequiredException,
    # ProxyAuthenticationRequiredException,
    # RangeNotSatisfiableException,
    # RequestHeaderFieldsTooLargeException,
    # RequestTimeoutException,
    # TooManyRequestsException,
    # UnavailableForLegalReasonsException,
    # UnprocessableEntityException,
    # UnsupportedMediaTypeException,
    # UpgradeRequiredException,
    # UriTooLongException,
    # NoResponseException,
    # RequestHeaderTooLargeException,
    # SSLCertificateErrorException,
    # SSLCertificateRequiredException,
    # HttpRequestSentToHttpsException,
    # ClientClosedRequestException,
]

SERVER_EXCEPTIONS = [
    InternalServerErrorException,
    ServerException,
    # BadGatewayException,
    # BandwidthLimitExceededException,
    # ConnectionTimeoutException,
    # GatewayTimeoutException,
    # HttpVersionNotSupportedException,
    # InsufficientStorageException,
    # InvalidSSLCertificateException,
    # LoopDetectedException,
    # NetworkAuthenticationRequiredException,
    # NetworkReadTimeoutException,
    # NotExtendedException,
    # NotImplementedException,
    # OriginDNSErrorException,
    # RailgunErrorException,
    # ServiceUnavailableException,
    # SSLHandshakeFailedException,
    # TimeoutOccurredException,
    # UnknownErrorException,
    # UnreachableOriginException,
    # VariantAlsoNegotiatesException,
    # WebServerIsDownException,
]

CLIENT_EXCEPTIONS_MAP = {
    400: BadRequestException,
    401: UnauthorizedException,
    403: ForbiddenException,
    404: NotFoundException,
    # 402: PaymentRequiredException,
    # 405: MethodNotAllowedException,
    # 406: NotAcceptableException,
    # 407: ProxyAuthenticationRequiredException,
    # 408: RequestTimeoutException,
    # 409: ConflictException,
    # 410: GoneException,
    # 411: LengthRequiredException,
    # 412: PreconditionFailedException,
    # 413: PayloadTooLargeException,
    # 414: UriTooLongException,
    # 415: UnsupportedMediaTypeException,
    # 416: RangeNotSatisfiableException,
    # 417: ExpectationFailedException,
    # 418: ImATeapotException,
    # 421: MisdirectedRequestException,
    # 422: UnprocessableEntityException,
    # 423: LockedException,
    # 424: FailedDependencyException,
    # 426: UpgradeRequiredException,
    # 428: PreconditionRequiredException,
    # 429: TooManyRequestsException,
    # 431: RequestHeaderFieldsTooLargeException,
    # 444: NoResponseException,
    # 451: UnavailableForLegalReasonsException,
    # 494: RequestHeaderTooLargeException,
    # 495: SSLCertificateErrorException,
    # 496: SSLCertificateRequiredException,
    # 497: HttpRequestSentToHttpsException,
    # 499: ClientClosedRequestException,
}

SERVER_EXCEPTIONS_MAP = {
    500: InternalServerErrorException,
    # 501: NotImplementedException,
    # 502: BadGatewayException,
    # 503: ServiceUnavailableException,
    # 504: GatewayTimeoutException,
    # 505: HttpVersionNotSupportedException,
    # 506: VariantAlsoNegotiatesException,
    # 507: InsufficientStorageException,
    # 508: LoopDetectedException,
    # 509: BandwidthLimitExceededException,
    # 510: NotExtendedException,
    # 511: NetworkAuthenticationRequiredException,
    # 520: UnknownErrorException,
    # 521: WebServerIsDownException,
    # 522: ConnectionTimeoutException,
    # 523: UnreachableOriginException,
    # 524: TimeoutOccurredException,
    # 525: SSLHandshakeFailedException,
    # 526: InvalidSSLCertificateException,
    # 527: RailgunErrorException,
    # 530: OriginDNSErrorException,
    # 598: NetworkReadTimeoutException,
}

HTTP_EXCEPTIONS = CLIENT_EXCEPTIONS + SERVER_EXCEPTIONS
HTTP_EXCEPTIONS_MAP: Mapping[int, Union[Type[ServerException], Type[ClientException]]] = {**SERVER_EXCEPTIONS_MAP, **CLIENT_EXCEPTIONS_MAP}

ALL_EXCEPTION_CLASSES = [
    # DataException,
    # IntegrityException,
    # InvalidApiParameterException,
    # InvalidEncodingException,
    # InvalidParameterException,
    # InvalidUrlException,
    # MessageToBeRequeuedException,
    # OperationalException,
    # ResourceAlreadyExistsException,
    # UrlJoinException,
    # TimeoutException,
    # LockTimeoutException,
    # CleaningUrlException,
    # MissingExecutorException,
    # DuplicateJobTypeException,
    # JobNotFoundException,
    # TypeNotFoundException,
    # SignalTimeoutAlreadySetException,
    # SqsSendingFaultException,
] + HTTP_EXCEPTIONS
