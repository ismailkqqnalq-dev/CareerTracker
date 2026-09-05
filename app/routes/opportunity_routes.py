from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import opportunity
from app.services import opportunity_service as service
from app.schemas.opportunity import OpportunityCreate, OpportunityResponse, OpportunityUpdate

router=APIRouter()
@router.post("/opportunities",response_model=OpportunityResponse)
def create_opportunity(opportunity:OpportunityCreate, db:Session=Depends(get_db)):
    result=service.create_opportunity(db, opportunity.model_dump())
    return result

@router.get("/opportunities", response_model=list[OpportunityResponse])
def get_all_opportunities(db:Session=Depends(get_db)):
    return service.get_all_opportunities(db)

@router.get("/opportunities/{opportunity_id}",response_model=OpportunityResponse)
def get_opportunity(opportunity_id:int, db:Session=Depends(get_db)):
    opportunity=service.get_opportunity_by_id(db, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return opportunity

@router.patch("/opportunities/{opportunity_id}",response_model=OpportunityResponse)
def update_opportunity(opportunity_id:int, update_data:OpportunityUpdate, db:Session=Depends(get_db)):
    updated_opportunity = service.update_opportunity(
        db, opportunity_id, update_data.model_dump(exclude_unset=True)
    )
    return updated_opportunity
@router.delete("/opportunities/{opportunity_id}")
def delete_opportunity(opportunity_id:int, db:Session=Depends(get_db)):
    result=service.delete_opportunity(db, opportunity_id)
    if result:
        return {"message": "Opportunity deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Opportunity not found")