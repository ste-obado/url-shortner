from database import  get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,HTTPException,status
from protection import get_current_user
from models import URL
from schema import URL
from dependencies import generate_code


router=APIRouter(
    prefix="/url_shortner",
    tags=["URL Shortening"]
)

@router.post("/shorten")
def shorten_url(url: URL, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Check if the URL already exists in the database
    existing_url = db.query(URL).filter(URL.original_url == url.original_url).first()
    if existing_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL already shortened")

    # Create a new URL entry in the database
    new_url = URL(
        original_url=url.original_url,
        owner_id=current_user.id  # Associate the URL with the current user
    )
    db.add(new_url)
    db.commit()
    db.refresh(new_url)

    #generate code with database id
    code=generate_code(existing_url.id)

    new_code = URL(
            # Associate the URL with the current user
            Code=code
        )
    db.add(new_code)
    db.commit()
    db.refresh(new_code)

    return {"original_url": new_url.original_url, 
            "shortened_code":new_url.Code}