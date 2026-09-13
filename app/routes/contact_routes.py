from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services import contact_service as service
from app.schemas.contacts import ContactCreate, ContactResponse, ContactUpdate

router=APIRouter()
@router.post("/contacts", response_model=ContactResponse)
def create_contact(contact:ContactCreate, db:Session=Depends(get_db)):
    result=service.create_contact(db, contact.model_dump())
    return result 

@router.get("/contacts", response_model=list[ContactResponse])
def get_all_contacts(db:Session=Depends(get_db)):
    return service.get_all_contacts(db)

@router.get("/contacts/{contact_id:int}", response_model=ContactResponse)
def get_contact(contact_id:int, db:Session=Depends(get_db)):
    contact=service.get_contact_by_id(db, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.patch("/contacts/{contact_id:int}", response_model=ContactResponse)
def update_contact(contact_id:int, update_data:ContactUpdate, db:Session=Depends(get_db)):
    updated_contact = service.update_contact(
        db, contact_id, update_data.model_dump(exclude_unset=True)
        )
    return updated_contact

@router.delete("/contacts/{contact_id:int}")
def delete_contact(contact_id:int, db:Session=Depends(get_db)):
    result=service.delete_contact(db, contact_id)
    if result:
        return {"message": "Contact deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Contact not found")
    
