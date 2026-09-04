from app.repositories import opportunity_repository as op

def create_opportunity(db, opportunity_data):
    return op.create_opportunity(db, opportunity_data)

def get_all_opportunities(db):
    return op.get_all_opportunities(db)

def get_opportunity_by_id(db, opportunity_id):
    return op.get_opportunity_by_id(db,opportunity_id)

def update_opportunity(db, opportunity_id, update_data):
    return op.update_opportunity(db, opportunity_id, update_data)

def delete_opportunity(db, opportunity_id):
    return op.delete_opportunity(db, opportunity_id)