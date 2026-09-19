from app.database.session import Base 
from app.database.session import engine
from app.models.opportunity import Opportunity
from app.models.contacts import Contact
from app.models.activities import Activity
Base.metadata.create_all(bind=engine)
