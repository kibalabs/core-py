from fastapi import APIRouter


def create_api(name: str, version: str, environment: str) -> APIRouter:
    router = APIRouter()

    @router.get('/')
    async def root() -> dict[str, str]:
        return {'server': name, 'version': version, 'environment': environment}

    return router
