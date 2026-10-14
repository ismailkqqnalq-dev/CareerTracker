from app.repositories import contact_repository as cp
from app.repositories import opportunity_repository as op


def _require_owned_opportunity(db, opportunity_id, user_id):
    if opportunity_id is None:
        raise ValueError("Opportunity ID cannot be null")

    opportunity = op.get_opportunity_by_id(
        db,
        opportunity_id,
        user_id=user_id,
    )
    if opportunity is None:
        raise LookupError("Opportunity not found")

    return opportunity


def create_contact(db, contact_data, user_id):
    _require_owned_opportunity(
        db,
        contact_data.get("opportunity_id"),
        user_id,
    )
    return cp.create_contact(db, contact_data, user_id=user_id)


def get_contact_by_id(db, contact_id, user_id):
    return cp.get_contact_by_id(db, contact_id, user_id=user_id)


def get_all_contacts(db, user_id):
    return cp.get_all_contacts(db, user_id=user_id)


def update_contact(db, contact_id, contact_data, user_id):
    contact = cp.get_contact_by_id(db, contact_id, user_id=user_id)
    if contact is None:
        raise LookupError("Contact not found")

    if "opportunity_id" in contact_data:
        _require_owned_opportunity(
            db,
            contact_data["opportunity_id"],
            user_id,
        )

    return cp.update_contact(
        db,
        contact_id,
        contact_data,
        user_id=user_id,
    )


def delete_contact(db, contact_id, user_id):
    return cp.delete_contact(db, contact_id, user_id=user_id)