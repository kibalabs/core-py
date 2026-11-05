import pydantic
import pytest

from core.util.typing_util import UuidString


class _Model(pydantic.BaseModel):
    uuid: UuidString


class TestUuidString:

    @pytest.mark.parametrize('value', ['0e1f2a3b-4c5d-4e6f-8a7b-9c0d1e2f3a4b', 'A0B1C2D3-E4F5-4A6B-8C7D-0E1F2A3B4C5D'])
    def test_keeps_hyphenated_uuids_as_given(self, value: str) -> None:
        assert _Model(uuid=value).uuid == value

    @pytest.mark.parametrize('value', ['not-a-uuid', '0e1f2a3b4c5d4e6f8a7b9c0d1e2f3a4b', '{0e1f2a3b-4c5d-4e6f-8a7b-9c0d1e2f3a4b}', '0e1f2a3b-4c5d-4e6f-8a7b-9c0d1e2f3a4b0', ''])
    def test_rejects_other_strings(self, value: str) -> None:
        with pytest.raises(pydantic.ValidationError):
            _Model(uuid=value)
