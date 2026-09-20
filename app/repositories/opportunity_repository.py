from sqlalchemy.orm import Session
from app.models.opportunity import Opportunity
from sqlalchemy import func

def create_opportunity(db, opportunity_data):
    new_opportunity= Opportunity(**opportunity_data)
    db.add(new_opportunity)
    db.commit()
    return new_opportunity
def get_all_opportunities(db):
    return db.query(Opportunity).all()
def get_opportunity_by_id(db, opportunity_id):
    return db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
def update_opportunity(db, opportunity_id, update_data):
    opportunity= db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
    if opportunity:
        for key, value in update_data.items():
            setattr(opportunity, key, value)
        db.commit()
        db.refresh(opportunity)
        return opportunity
    return None
def delete_opportunity(db, opportunity_id):
    opportunity= db.query(Opportunity).filter(Opportunity.id==opportunity_id).first()
    if opportunity:
        db.delete(opportunity)
        db.commit()
        return True
    return False

def get_dashboard_stats(db):
    total=db.query(func.count(Opportunity.id)).scalar()
    by_status = db.query(Opportunity.status, func.count(Opportunity.id)).group_by(Opportunity.status).all()
    by_company = db.query(Opportunity.company, func.count(Opportunity.id)).group_by(Opportunity.company).all()
    by_status_dict = dict(by_status)

    interview_count = (
    by_status_dict.get("Ön görüşme", 0)
    + by_status_dict.get("Teknik mülakat", 0)
    + by_status_dict.get("Son mülakat", 0)
    )
    offer_count = by_status_dict.get("Teklif", 0)
    rejected_count = by_status_dict.get("Reddedildi", 0)

    rejection_rate = (rejected_count / total * 100) if total > 0 else 0
    return {
    "total_opportunities": total,
    "by_status": by_status_dict,
    "by_company": dict(by_company),
    "interview_count": interview_count,
    "offer_count": offer_count,
    "rejection_rate": round(rejection_rate, 2)
}