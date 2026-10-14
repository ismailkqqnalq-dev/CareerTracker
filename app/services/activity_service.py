from app.repositories import activity_repository as ap
from app.repositories import contact_repository as cp
from app.repositories import opportunity_repository as op


def _validate_links(db, opportunity_id, contact_id, user_id):
    if opportunity_id is None:
        raise ValueError("Opportunity ID cannot be null")

    opportunity = op.get_opportunity_by_id(
        db,
        opportunity_id,
        user_id=user_id,
    )
    if opportunity is None:
        raise LookupError("Opportunity not found")

    if contact_id is None:
        return

    contact = cp.get_contact_by_id(
        db,
        contact_id,
        user_id=user_id,
    )
    if contact is None:
        raise LookupError("Contact not found")

    if contact.opportunity_id != opportunity_id:
        raise ValueError("Contact does not belong to this opportunity")


def create_activity(db, activity_data, user_id):
    _validate_links(
        db,
        activity_data.get("opportunity_id"),
        activity_data.get("contact_id"),
        user_id,
    )
    return ap.create_activity(db, activity_data, user_id=user_id)


def get_all_activities(db, user_id):
    return ap.get_all_activities(db, user_id=user_id)


def get_activity_by_id(db, activity_id, user_id):
    return ap.get_activity_by_id(db, activity_id, user_id=user_id)


def update_activity(db, activity_id, activity_data, user_id):
    activity = ap.get_activity_by_id(db, activity_id, user_id=user_id)
    if activity is None:
        raise LookupError("Activity not found")

    opportunity_id = activity_data.get(
        "opportunity_id",
        activity.opportunity_id,
    )
    contact_id = activity_data.get(
        "contact_id",
        activity.contact_id,
    )

    _validate_links(db, opportunity_id, contact_id, user_id)

    return ap.update_activity(
        db,
        activity_id,
        activity_data,
        user_id=user_id,
    )


def delete_activity(db, activity_id, user_id):
    return ap.delete_activity(db, activity_id, user_id=user_id)