from __future__ import annotations

import base64
import dataclasses
import datetime
import typing

from core.util import json_util
from core.util.typing_util import JsonObject

JwtType = typing.TypeVar('JwtType', bound='Jwt')


@dataclasses.dataclass
class Jwt:
    headerDict: JsonObject = dataclasses.field(default_factory=dict)
    payloadDict: JsonObject = dataclasses.field(default_factory=dict)
    signatureBytes: bytes = b''

    @property
    def headerBase64(self) -> str:  # noqa: N802
        return Jwt._base64encode_string(value=json_util.dumps(obj=self.headerDict))

    @property
    def payloadBase64(self) -> str:  # noqa: N802
        return Jwt._base64encode_string(value=json_util.dumps(obj=self.payloadDict))

    @property
    def signatureBase64(self) -> str:  # noqa: N802
        return Jwt._base64encode(value=self.signatureBytes).decode()

    @property
    def verificationString(self) -> str:  # noqa: N802
        return f'{self.headerBase64}.{self.payloadBase64}'

    def to_string(self) -> str:
        return f'{self.headerBase64}.{self.payloadBase64}.{self.signatureBase64}'

    @classmethod
    def from_string(cls, jwtString: str) -> typing.Self:
        # NOTE(krish): jwts should not have the b64 padding included (its lossless to remove).
        # python complains if its missing, but not if there's too much, hence the wierd command below
        jwtParts = jwtString.split('.')
        headerDict = typing.cast(JsonObject, json_util.loads(Jwt._base64decode_string(value=jwtParts[0])))
        payloadDict = typing.cast(JsonObject, json_util.loads(Jwt._base64decode_string(value=jwtParts[1])))
        signatureBytes = Jwt._base64decode(value=jwtParts[2].encode())
        return cls(headerDict=headerDict, payloadDict=payloadDict, signatureBytes=signatureBytes)

    @classmethod
    def from_jwt(cls, jwt: Jwt) -> typing.Self:
        return cls.from_string(jwtString=jwt.to_string())

    @staticmethod
    def _base64decode_string(value: str, shouldAddPadding: bool = True) -> str:
        return Jwt._base64decode(value=value.encode(), shouldAddPadding=shouldAddPadding).decode()

    @staticmethod
    def _base64decode(value: bytes, shouldAddPadding: bool = True) -> bytes:
        if shouldAddPadding:
            remainder = len(value) % 4
            if remainder > 0:
                value += b'=' * (4 - remainder)
        return base64.urlsafe_b64decode(value)

    @staticmethod
    def _base64encode_string(value: str, shouldRemovePadding: bool = True) -> str:
        return Jwt._base64encode(value=value.encode(), shouldRemovePadding=shouldRemovePadding).decode()

    @staticmethod
    def _base64encode(value: bytes, shouldRemovePadding: bool = True) -> bytes:
        value = base64.urlsafe_b64encode(value)
        return value.rstrip(b'=') if shouldRemovePadding else value


@dataclasses.dataclass
class KibaJwt(Jwt):
    class Key:
        ALGORITHM = 'alg'
        TYPE = 'typ'
        KEY_ID = 'kid'
        TOKEN_ID = 'tid'
        USER_ID = 'sub'
        USER_NAME = 'nam'
        ISSUE_DATE = 'iat'
        EXPIRY_DATE = 'exp'
        FINAL_REFRESH_DATE = 'frd'

    @property
    def algorithm(self) -> str | None:
        return typing.cast(str, self.headerDict.get(KibaJwt.Key.ALGORITHM))

    @property
    def keyId(self) -> str | None:  # noqa: N802
        return typing.cast(str, self.headerDict.get(KibaJwt.Key.KEY_ID))

    @property
    def tokenId(self) -> str | None:  # noqa: N802
        return typing.cast(str, self.payloadDict[KibaJwt.Key.TOKEN_ID]) if self.payloadDict.get(KibaJwt.Key.TOKEN_ID) else None

    @property
    def userId(self) -> str | None:  # noqa: N802
        return typing.cast(str, self.payloadDict[KibaJwt.Key.USER_ID]) if self.payloadDict.get(KibaJwt.Key.USER_ID) else None

    @property
    def expiryDate(self) -> datetime.datetime | None:  # noqa: N802
        expiryDateSeconds = typing.cast(int, self.payloadDict.get('exp') or 0)
        return datetime.datetime.fromtimestamp(expiryDateSeconds, tz=datetime.UTC) if expiryDateSeconds else None

    @expiryDate.setter
    def expiryDate(self, expiryDate: datetime.datetime) -> None:  # noqa: N802
        self.payloadDict[KibaJwt.Key.EXPIRY_DATE] = int(expiryDate.timestamp())

    @property
    def issueDate(self) -> datetime.datetime | None:  # noqa: N802
        issueDateSeconds = typing.cast(int, self.payloadDict.get(KibaJwt.Key.ISSUE_DATE) or 0)
        return datetime.datetime.fromtimestamp(issueDateSeconds, tz=datetime.UTC) if issueDateSeconds else None

    @issueDate.setter
    def issueDate(self, issueDate: datetime.datetime) -> None:  # noqa: N802
        self.payloadDict[KibaJwt.Key.ISSUE_DATE] = int(issueDate.timestamp())

    @property
    def finalRefreshDate(self) -> datetime.datetime | None:  # noqa: N802
        finalRefreshDateSeconds = typing.cast(int, self.payloadDict.get(KibaJwt.Key.FINAL_REFRESH_DATE) or 0)
        return datetime.datetime.fromtimestamp(finalRefreshDateSeconds, tz=datetime.UTC) if finalRefreshDateSeconds else None

    @finalRefreshDate.setter
    def finalRefreshDate(self, finalRefreshDate: datetime.datetime) -> None:  # noqa: N802
        self.payloadDict[KibaJwt.Key.FINAL_REFRESH_DATE] = int(finalRefreshDate.timestamp())
