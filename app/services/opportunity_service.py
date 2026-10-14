from app.repositories import opportunity_repository as op


def create_opportunity(db, opportunity_data, user_id):
    return op.create_opportunity(db, opportunity_data, user_id)


def get_all_opportunities(db, user_id):
    return op.get_all_opportunities(db, user_id)


def get_opportunity_by_id(db, opportunity_id, user_id):
    return op.get_opportunity_by_id(db, opportunity_id, user_id)


def update_opportunity(db, opportunity_id, update_data, user_id):
    return op.update_opportunity(db, opportunity_id, update_data, user_id)


def delete_opportunity(db, opportunity_id, user_id):
    return op.delete_opportunity(db, opportunity_id, user_id)


def get_dashboard_stats(db, user_id):
    return op.get_dashboard_stats(db, user_id)