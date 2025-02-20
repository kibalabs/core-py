from __future__ import annotations

import base64
from binascii import Error as BinasciiError

from core.exceptions import UnauthorizedException


class BasicAuthentication:
    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    @classmethod
    def from_string(cls, basicAuthenticationString: str) -> BasicAuthentication:
        try:
            decodedString = base64.b64decode(s=basicAuthenticationString.encode('utf-8'))
        except BinasciiError as exception:
            raise UnauthorizedException(message='Failed to decode BasicAuthentication value.') from exception
        parts = decodedString.split(b':')
        return cls(username=parts[0].decode('latin1'), password=parts[1].decode('latin1'))

    def to_string(self) -> str:
        basicAuthenticationString = b':'.join((self.username.encode('latin1'), self.password.encode('latin1')))
        return base64.b64encode(s=basicAuthenticationString).decode('utf-8')
