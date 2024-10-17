from __future__ import annotations

import base64
import dataclasses
import datetime
import json
import typing

JwtType = typing.TypeVar('JwtType', bound='Jwt')  # pylint: disable=invalid-name

@dataclasses.dataclass
class Jwt:
    headerDict: dict[str, str] = dataclasses.field(default_factory=dict)
    payloadDict: dict[str, str | int] = dataclasses.field(default_factory=dict)
    signatureBytes: bytes = b''

    @property
    def headerBase64(self) -> str:
        return Jwt._base64encode_string(value=json.dumps(obj=self.headerDict, separators=(',', ':')))

    @property
    def payloadBase64(self) -> str:
        return Jwt._base64encode_string(value=json.dumps(obj=self.payloadDict, separators=(',', ':')))

    @property
    def signatureBase64(self) -> str:
        return Jwt._base64encode(value=self.signatureBytes).decode()

    @property
    def verificationString(self) -> str:
        return f'{self.headerBase64}.{self.payloadBase64}'

    def to_string(self) -> str:
        return f'{self.headerBase64}.{self.payloadBase64}.{self.signatureBase64}'

    @classmethod
    def from_string(cls: type[JwtType], jwtString: str) -> JwtType:
        # NOTE(krish): jwts should not have the b64 padding included (its lossless to remove).
        # python complains if its missing, but not if there's too much, hence the wierd command below
        jwtParts = jwtString.split('.')
        headerDict = json.loads(s=Jwt._base64decode_string(value=jwtParts[0]))
        payloadDict = json.loads(s=Jwt._base64decode_string(value=jwtParts[1]))
        signatureBytes = Jwt._base64decode(value=jwtParts[2].encode())
        return cls(headerDict=headerDict, payloadDict=payloadDict, signatureBytes=signatureBytes)

    @classmethod
    def from_jwt(cls: type[JwtType], jwt: Jwt) -> JwtType:
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
        return self.headerDict.get(KibaJwt.Key.ALGORITHM)

    @property
    def keyId(self) -> str | None:
        return self.headerDict.get(KibaJwt.Key.KEY_ID)

    @property
    def tokenId(self) -> str | None:
        return typing.cast(str, self.payloadDict[KibaJwt.Key.TOKEN_ID]) if self.payloadDict.get(KibaJwt.Key.TOKEN_ID) else None

    @property
    def userId(self) -> str | None:
        return typing.cast(str, self.payloadDict[KibaJwt.Key.USER_ID]) if self.payloadDict.get(KibaJwt.Key.USER_ID) else None

    @property
    def expiryDate(self) -> datetime.datetime | None:
        expiryDateSeconds = typing.cast(int, self.payloadDict.get('exp') or 0)
        return datetime.datetime.fromtimestamp(expiryDateSeconds, tz=datetime.timezone.utc) if expiryDateSeconds else None

    @expiryDate.setter
    def expiryDate(self, expiryDate: datetime.datetime) -> None:
        self.payloadDict[KibaJwt.Key.EXPIRY_DATE] = int(expiryDate.timestamp())

    @property
    def issueDate(self) -> datetime.datetime | None:
        issueDateSeconds = typing.cast(int, self.payloadDict.get(KibaJwt.Key.ISSUE_DATE) or 0)
        return datetime.datetime.fromtimestamp(issueDateSeconds, tz=datetime.timezone.utc) if issueDateSeconds else None

    @issueDate.setter
    def issueDate(self, issueDate: datetime.datetime) -> None:
        self.payloadDict[KibaJwt.Key.ISSUE_DATE] = int(issueDate.timestamp())

    @property
    def finalRefreshDate(self) -> datetime.datetime | None:
        finalRefreshDateSeconds = typing.cast(int, self.payloadDict.get(KibaJwt.Key.FINAL_REFRESH_DATE) or 0)
        return datetime.datetime.fromtimestamp(finalRefreshDateSeconds, tz=datetime.timezone.utc) if finalRefreshDateSeconds else None

    @finalRefreshDate.setter
    def finalRefreshDate(self, finalRefreshDate: datetime.datetime) -> None:
        self.payloadDict[KibaJwt.Key.FINAL_REFRESH_DATE] = int(finalRefreshDate.timestamp())

    # @property
    # def scopes(self) -> Sequence[str]:
    #     return typing.cast(Sequence[str], self.payloadDict.get(KibaJwt.Key.SCOPES) or [])

    # @scopes.setter
    # def scopes(self, scopes: Sequence[str]) -> None:
    #     self.payloadDict[KibaJwt.Key.SCOPES] = scopes
