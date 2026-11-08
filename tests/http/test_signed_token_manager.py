import datetime

import pytest

from core.exceptions import UnauthorizedException
from core.http.jwt import KibaJwt
from core.http.signed_token_manager import SignedTokenManager

LIFETIME = datetime.timedelta(minutes=5)


def test_a_token_round_trips_its_claims() -> None:
    tokenManager = SignedTokenManager(secret='secret', keyId='test-v1')
    jwt = tokenManager.validate_token(tokenString=tokenManager.create_token(tokenType='state', lifetime=LIFETIME, claims={'sub': 'user-1'}), tokenType='state')
    assert jwt.userId == 'user-1'
    assert jwt.tokenId


def test_each_token_gets_its_own_token_id() -> None:
    tokenManager = SignedTokenManager(secret='secret', keyId='test-v1')
    tokenIds = {tokenManager.validate_token(tokenString=tokenManager.create_token(tokenType='state', lifetime=LIFETIME, claims={}), tokenType='state').tokenId for _ in range(3)}
    assert len(tokenIds) == 3


@pytest.mark.parametrize(
    ('validatingManager', 'tokenType', 'message'),
    [
        (SignedTokenManager(secret='other-secret', keyId='test-v1'), 'state', 'INVALID_TOKEN'),
        (SignedTokenManager(secret='secret', keyId='other-v1'), 'state', 'INVALID_TOKEN'),
        (SignedTokenManager(secret='secret', keyId='test-v1'), 'code', 'INVALID_TOKEN_TYPE'),
    ],
)
def test_a_token_is_rejected_by_another_secret_key_or_type(validatingManager: SignedTokenManager, tokenType: str, message: str) -> None:
    token = SignedTokenManager(secret='secret', keyId='test-v1').create_token(tokenType='state', lifetime=LIFETIME, claims={})
    with pytest.raises(UnauthorizedException, match=message):
        validatingManager.validate_token(tokenString=token, tokenType=tokenType)


def test_an_expired_token_is_rejected() -> None:
    tokenManager = SignedTokenManager(secret='secret', keyId='test-v1')
    token = tokenManager.create_token(tokenType='state', lifetime=datetime.timedelta(seconds=-1), claims={})
    with pytest.raises(UnauthorizedException, match='TOKEN_EXPIRED'):
        tokenManager.validate_token(tokenString=token, tokenType='state')


def test_a_tampered_payload_is_rejected() -> None:
    tokenManager = SignedTokenManager(secret='secret', keyId='test-v1')
    jwt = KibaJwt.from_string(jwtString=tokenManager.create_token(tokenType='state', lifetime=LIFETIME, claims={'sub': 'user-1'}))
    jwt.payloadDict['sub'] = 'user-2'
    with pytest.raises(UnauthorizedException, match='INVALID_TOKEN'):
        tokenManager.validate_token(tokenString=jwt.to_string(), tokenType='state')


@pytest.mark.parametrize('tokenString', ['W10.e30.AA', 'e30.W10.AA', 'not-a-jwt', 'a.b.c'])
def test_a_malformed_token_is_rejected(tokenString: str) -> None:
    with pytest.raises(UnauthorizedException, match='INVALID_TOKEN'):
        SignedTokenManager(secret='secret', keyId='test-v1').validate_token(tokenString=tokenString, tokenType='state')
