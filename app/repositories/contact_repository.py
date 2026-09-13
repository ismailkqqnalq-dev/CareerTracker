from sqlalchemy.orm import Session
from app.models.contacts import Contact

def create_contact(db,contact_data):
    contact=Contact(**contact_data)
    db.add(contact)
    db.commit()
    return contact

def get_all_contacts(db):
    return db.query(Contact).all()

def get_contact_by_id(db, contact_id):
    return db.query(Contact).filter(Contact.id==contact_id).first()


def update_contact(db, contact_id, contact_data):
    contact = db.query(Contact).filter(Contact.id==contact_id).first()
    if contact:
        for key, value in contact_data.items():
            setattr(contact, key, value)
        db.commit()
        db.refresh(contact)
        return contact
    return None
def delete_contact(db, contact_id):
    contact=db.query(Contact).filter(Contact.id==contact_id).first()
    if contact:
        db.delete(contact)
        db.commit()
        return True
    return False