from fastapi.routing import APIRouter

from core.api.kiba_route import KibaRoute


class KibaRouter(APIRouter):

    def __init__(self) -> None:
        super().__init__(route_class=KibaRoute)
