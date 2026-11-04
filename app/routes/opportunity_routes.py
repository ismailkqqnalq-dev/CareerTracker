import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.pagination import pagination_params, set_total_count
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
)
from app.services import opportunity_service as service


router = APIRouter()


@router.post("/opportunities", response_model=OpportunityResponse)
def create_opportunity(
    opportunity: OpportunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_opportunity(
        db,
        opportunity.model_dump(),
        user_id=current_user.id,
    )


@router.get("/opportunities", response_model=list[OpportunityResponse])
def get_all_opportunities(
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = service.get_all_opportunities(
        db, user_id=current_user.id, limit=pagination[0], offset=pagination[1]
    )
    set_total_count(response, total)
    return items


def _safe_csv_cell(value):
    if not isinstance(value, str):
        return value
    first_after_spaces = value.lstrip(" ")[:1]
    first_non_whitespace = value.lstrip()[:1]
    if (
        first_after_spaces in {"\t", "\r", "\n"}
        or first_non_whitespace in {"=", "+", "-", "@"}
    ):
        return "'" + value
    return value


def _csv_rows(opportunities):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    yield "\ufeff"
    writer.writerow([
        "id", "company", "position", "type", "status", "salary",
        "location", "application_date",
    ])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for opportunity in opportunities:
        writer.writerow([
            _safe_csv_cell(value)
            for value in (
                opportunity.id,
                opportunity.company,
                opportunity.position,
                opportunity.type,
                opportunity.status,
                opportunity.salary,
                opportunity.location,
                opportunity.application_date,
            )
        ])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


@router.get("/opportunities/export")
def export_opportunities_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return StreamingResponse(
        _csv_rows(service.iter_opportunities(db, user_id=current_user.id)),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=careertracker_export.csv"
        },
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = service.get_opportunity_by_id(
        db,
        opportunity_id,
        user_id=current_user.id,
    )
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return opportunity


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def update_opportunity(
    opportunity_id: int,
    update_data: OpportunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = service.update_opportunity(
        db,
        opportunity_id,
        update_data.model_dump(exclude_unset=True),
        user_id=current_user.id,
    )
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return opportunity


@router.delete("/opportunities/{opportunity_id}")
def delete_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = service.delete_opportunity(
        db,
        opportunity_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    return {"message": "Opportunity deleted successfully"}


@router.get("/dashboard")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_dashboard_stats(db, user_id=current_user.id)
    
