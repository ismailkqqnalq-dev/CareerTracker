from app.repositories import activity_repository as ap

def create_activity(db, activity_data):
    return ap.create_activity(db, activity_data)

def get_all_activities(db):
    return ap.get_all_activities(db)

def get_activity_by_id(db, activity_id):
    return ap.get_activity_by_id(db, activity_id)

def update_activity(db, activity_id, activity_data):
    return ap.update_activity(db, activity_id, activity_data)

def delete_activity(db, activity_id):
    return ap.delete_activity(db, activity_id)