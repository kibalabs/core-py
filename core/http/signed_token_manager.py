import datetime
import hashlib
import hmac
import uuid

from core.exceptions import UnauthorizedException
from core.http.jwt import KibaJwt
from core.util import date_util
from core.util.typing_util import JsonObject

TOKEN_TYPE_KEY = 'tty'


# NOTE(krishan711): HS256 JWTs typed by tokenType so a token issued for one purpose can't be used for another. Each token
# has a tokenId, so pair it with an AuthUsedTokenStore to make a token single-use
class SignedTokenManager:
    def __init__(self, secret: str, keyId: str) -> None:
        self._secret = secret.encode('utf-8')
        self.keyId = keyId

    def create_token(self, tokenType: str, lifetime: datetime.timedelta, claims: JsonObject) -> str:
        issueDate = date_util.datetime_from_now()
        jwt = KibaJwt(
            headerDict={KibaJwt.Key.ALGORITHM: 'HS256', KibaJwt.Key.TYPE: 'JWT', KibaJwt.Key.KEY_ID: self.keyId},
            payloadDict={
                **claims,
                KibaJwt.Key.TOKEN_ID: str(uuid.uuid4()),
                TOKEN_TYPE_KEY: tokenType,
                KibaJwt.Key.ISSUE_DATE: int(issueDate.timestamp()),
                KibaJwt.Key.EXPIRY_DATE: int((issueDate + lifetime).timestamp()),
            },
        )
        jwt.signatureBytes = self._sign(jwt=jwt)
        return jwt.to_string()

    def validate_token(self, tokenString: str, tokenType: str) -> KibaJwt:
        try:
            jwt = KibaJwt.from_string(jwtString=tokenString)
        except Exception as exception:
            raise UnauthorizedException(message='INVALID_TOKEN') from exception
        if not isinstance(jwt.headerDict, dict) or not isinstance(jwt.payloadDict, dict):
            raise UnauthorizedException(message='INVALID_TOKEN')
        if jwt.algorithm != 'HS256' or jwt.keyId != self.keyId or not hmac.compare_digest(jwt.signatureBytes, self._sign(jwt=jwt)):
            raise UnauthorizedException(message='INVALID_TOKEN')
        if jwt.payloadDict.get(TOKEN_TYPE_KEY) != tokenType:
            raise UnauthorizedException(message='INVALID_TOKEN_TYPE')
        expiryDate = jwt.expiryDate
        if not expiryDate or expiryDate <= date_util.datetime_from_now():
            raise UnauthorizedException(message='TOKEN_EXPIRED')
        return jwt

    def _sign(self, jwt: KibaJwt) -> bytes:
        return hmac.new(self._secret, jwt.verificationString.encode('utf-8'), hashlib.sha256).digest()
