from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DB, CurrentUser, allow
from app.core.permissions import Permissions
from app.models.resource_allocation import ResourceAllocation
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.schemas.common import Page, UTCDateTime
from app.schemas.resource_allocation import AllocationCreate, AllocationOut, AvailableResource
from app.utils.enums import AssignmentStatus, ResourceType
from app.utils.filters import DateRangeParams
from app.utils.pagination import PageParams, page_params, paginate
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["Resource Allocation"])


@router.post("/allocate", response_model=AllocationOut, status_code=201,
             summary="Allocate gate / counter / staff / equipment to a flight (conflict-checked)")
def allocate(data: AllocationCreate, db: DB, user: User = allow(Permissions.RESOURCE_ALLOCATE)):
    return ResourceService(db).allocate(data, user)


@router.post("/allocations/{allocation_id}/release", response_model=AllocationOut)
def release(allocation_id: int, db: DB, user: User = allow(Permissions.RESOURCE_ALLOCATE)):
    return ResourceService(db).release(allocation_id, user)


@router.get("/availability", response_model=list[AvailableResource], summary="Resources free in a time window")
def availability(db: DB, _: CurrentUser, resource_type: ResourceType, start_time: UTCDateTime = Query(...),
                 end_time: UTCDateTime = Query(...), terminal_id: int | None = None, airport_id: int | None = None):
    return ResourceService(db).availability(resource_type, start_time, end_time, terminal_id, airport_id)


@router.get("/allocations", response_model=Page[AllocationOut], summary="Allocation history")
def allocations(db: DB, _: CurrentUser, resource_type: ResourceType | None = None, resource_id: int | None = None,
                flight_id: int | None = None, status: AssignmentStatus | None = None,
                dates: DateRangeParams = Depends(), params: PageParams = Depends(page_params)):
    start, end = dates.bounds
    stmt = ResourceRepository(db).search(resource_type, resource_id, flight_id, status, start, end) \
        .order_by(ResourceAllocation.created_at.desc(), ResourceAllocation.id.desc())
    return paginate(db, stmt, params)


@router.get("/flight/{flight_id}", response_model=list[AllocationOut], summary="Active resources for a flight")
def flight_resources(flight_id: int, db: DB, _: CurrentUser):
    repo = ResourceRepository(db)
    return repo.list(repo.search(flight_id=flight_id, status=AssignmentStatus.ACTIVE))
