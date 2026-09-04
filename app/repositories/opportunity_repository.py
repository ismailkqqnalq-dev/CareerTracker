from sqlalchemy.orm import Session
from app.models.opportunity import Opportunity

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