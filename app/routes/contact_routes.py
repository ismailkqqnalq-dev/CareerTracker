from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database.session import get_db
from app.models.users import User
from app.schemas.contacts import ContactCreate, ContactResponse, ContactUpdate
from app.services import contact_service as service


router = APIRouter()


@router.post("/contacts", response_model=ContactResponse)
def create_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return service.create_contact(
            db,
            contact.model_dump(),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/contacts", response_model=list[ContactResponse])
def get_all_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_all_contacts(db, user_id=current_user.id)


@router.get("/contacts/{contact_id:int}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = service.get_contact_by_id(
        db,
        contact_id,
        user_id=current_user.id,
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@router.patch("/contacts/{contact_id:int}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    update_data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        contact = service.update_contact(
            db,
            contact_id,
            update_data.model_dump(exclude_unset=True),
            user_id=current_user.id,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")

    return contact


@router.delete("/contacts/{contact_id:int}")
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = service.delete_contact(
        db,
        contact_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")

    return {"message": "Contact deleted successfully"}