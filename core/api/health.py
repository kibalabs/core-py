from typing import Dict

from core.api.kiba_router import KibaRouter

def create_api(name: str, version: str) -> KibaRouter:
    router = KibaRouter()

    @router.get('/')
    async def root() -> Dict[str, str]:  # pylint: disable=unused-variable
        return {'server': name, 'version': version}

    return router
