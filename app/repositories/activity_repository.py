from sqlalchemy.orm import Session
from app.models.activities import Activity

def create_activity(db, activity_data):
    activity = Activity(**activity_data)
    db.add(activity)
    db.commit()
    return activity

def get_all_activities(db):
    return db.query(Activity).all()

def get_activity_by_id(db, activity_id):
    return db.query(Activity).filter(Activity.id == activity_id).first()

def update_activity(db, activity_id, activity_data):
    activity = db.query(Activity).filter(Activity.id==activity_id).first()
    if activity:
        for key, value in activity_data.items():
            setattr(activity, key, value)
        db.commit()
        db.refresh(activity)
        return activity
    return None

def delete_activity(db, activity_id):
    
    activity=db.query(Activity).filter(Activity.id==activity_id).first()
    if activity:
        db.delete(activity)
        db.commit()
        return True
    return False