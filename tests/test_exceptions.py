import datetime
import email.utils

from core.exceptions import HTTP_EXCEPTIONS_MAP
from core.exceptions import BadRequestException
from core.exceptions import RedirectException
from core.exceptions import TooManyRequestsException


class TestExceptionHeaderHooks:

    def test_default_from_headers_ignores_headers(self):
        exception = BadRequestException.from_headers(message='bad request', statusCode=400, headers={'Retry-After': '99'})
        assert exception.message == 'bad request'

    def test_default_outgoing_headers_is_empty(self):
        exception = BadRequestException(message='bad request')
        assert exception.outgoing_headers() == {}


class TestTooManyRequestsException:

    def test_from_headers_parses_delta_seconds(self):
        exception = TooManyRequestsException.from_headers(message='slow down', statusCode=429, headers={'Retry-After': '42'})
        assert exception.retryAfterSeconds == 42

    def test_from_headers_parses_http_date(self):
        futureDate = email.utils.format_datetime(datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=30))
        exception = TooManyRequestsException.from_headers(message='slow down', statusCode=429, headers={'Retry-After': futureDate})
        assert exception.retryAfterSeconds is not None
        assert 25 <= exception.retryAfterSeconds <= 30

    def test_from_headers_missing_header_is_none(self):
        exception = TooManyRequestsException.from_headers(message='slow down', statusCode=429, headers={})
        assert exception.retryAfterSeconds is None

    def test_from_headers_invalid_header_is_none(self):
        exception = TooManyRequestsException.from_headers(message='slow down', statusCode=429, headers={'Retry-After': 'not-a-value'})
        assert exception.retryAfterSeconds is None

    def test_from_headers_past_http_date_clamps_to_zero(self):
        pastDate = email.utils.format_datetime(datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=30))
        exception = TooManyRequestsException.from_headers(message='slow down', statusCode=429, headers={'Retry-After': pastDate})
        assert exception.retryAfterSeconds == 0

    def test_outgoing_headers_includes_retry_after_when_set(self):
        exception = TooManyRequestsException(message='slow down', retryAfterSeconds=42)
        assert exception.outgoing_headers() == {'Retry-After': '42'}

    def test_outgoing_headers_empty_when_not_set(self):
        exception = TooManyRequestsException(message='slow down')
        assert exception.outgoing_headers() == {}

    def test_dispatched_via_http_exceptions_map(self):
        exceptionCls = HTTP_EXCEPTIONS_MAP[429]
        exception = exceptionCls.from_headers(message='slow down', statusCode=429, headers={'Retry-After': '7'})
        assert isinstance(exception, TooManyRequestsException)
        assert exception.retryAfterSeconds == 7


class TestRedirectException:

    def test_outgoing_headers_without_cache_header(self):
        exception = RedirectException(location='https://example.com', statusCode=302, shouldAddCacheHeader=False)
        assert exception.outgoing_headers() == {'Location': 'https://example.com'}

    def test_outgoing_headers_with_cache_header(self):
        exception = RedirectException(location='https://example.com', statusCode=301, shouldAddCacheHeader=True)
        headers = exception.outgoing_headers()
        assert headers['Location'] == 'https://example.com'
        assert headers['Cache-Control'] == f'max-age={60 * 60 * 24 * 365}'
