from app.repositories import contact_repository as cp

def create_contact(db, contact_data):
    return cp.create_contact(db, contact_data)

def get_contact_by_id(db, contact_id):
    return cp.get_contact_by_id(db , contact_id)

def  get_all_contacts(db):
    return cp.get_all_contacts(db)

def delete_contact(db, contact_id):
    return cp.delete_contact(db, contact_id)

def update_contact(db, contact_id, contact_data):
    return cp.update_contact(db, contact_id, contact_data)