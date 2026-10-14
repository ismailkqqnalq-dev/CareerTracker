import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_all_opportunities(db, user_id=current_user.id)


@router.get("/opportunities/export")
def export_opportunities_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunities = service.get_all_opportunities(
        db,
        user_id=current_user.id,
    )

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "company",
        "position",
        "type",
        "status",
        "salary",
        "location",
        "application_date",
    ])

    for opportunity in opportunities:
        writer.writerow([
            opportunity.id,
            opportunity.company,
            opportunity.position,
            opportunity.type,
            opportunity.status,
            opportunity.salary,
            opportunity.location,
            opportunity.application_date,
        ])

    output.seek(0)
    return StreamingResponse(
        output,
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
    
