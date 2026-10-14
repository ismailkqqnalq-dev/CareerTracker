from app.models.contacts import Contact


def create_contact(db, contact_data, user_id):
    data = {**contact_data, "user_id": user_id}
    contact = Contact(**data)

    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def get_all_contacts(db, user_id):
    return (
        db.query(Contact)
        .filter(Contact.user_id == user_id)
        .all()
    )


def get_contact_by_id(db, contact_id, user_id):
    return (
        db.query(Contact)
        .filter(
            Contact.id == contact_id,
            Contact.user_id == user_id,
        )
        .first()
    )


def update_contact(db, contact_id, contact_data, user_id):
    contact = get_contact_by_id(db, contact_id, user_id)
    if contact is None:
        return None

    for key, value in contact_data.items():
        setattr(contact, key, value)

    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db, contact_id, user_id):
    contact = get_contact_by_id(db, contact_id, user_id)
    if contact is None:
        return False

    db.delete(contact)
    db.commit()
    return True