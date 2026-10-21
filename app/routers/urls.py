from database import  get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,HTTPException,status,Request,BackgroundTasks,RedirectResponse
from protection import get_current_user
from models import URL
from schema import URL
from dependencies import generate_code
from app.util.backgroudtask import record_click
from app.util.ratelimiter import rate_limit
from redis_cache import redis_client


router=APIRouter(
    prefix="/url_shortner",
    tags=["URL Shortening"]
)

@router.post("/shorten", dependencies=[Depends(rate_limit(10,60))])
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
    existing_custom_code=db.query(URL).filter(URL.custom_code ==  url.custom_code).first()
    if existing_custom_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Custom code already exists")
        
    else:
        code = url.custom_code

    #check if user needs a generated code 
    if url.custom_code is None:
        code = generate_code(new_url.id)    


    new_code = URL(
            # Associate the URL with the current user
            Code=code
        )
    db.add(new_code)
    db.commit()
    db.refresh(new_code)

    return {"original_url": new_url.original_url, 
            "shortened_code":new_url.Code}

@router.get("/{code}")
def redirect_to_original_url(code: str, request: Request, 
                             background_tasks: BackgroundTasks,
                              db: Session = Depends(get_db)):
    code_key=f"code:{code}"
    GET_CODE=redis_client.get(code_key)

    if GET_CODE:
        return RedirectResponse(url=GET_CODE, status_code=307)
    
    # Retrieve the original URL based on the shortened code
    url_entry = db.query(URL).filter(URL.Code == code).first()
    if not url_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortened URL not found")

    # request fro user_agent hearder
    user_agent = request.headers.get("User-Agent", "Unknown")

    #record click using background task
    background_tasks.add_task(record_click, short_code=code, user_agent=user_agent)

    redis_client.set(code_key,{"url":url_entry.original_url,"status":307})

    # Return the original URL for redirection
    return RedirectResponse(url=url_entry.original_url, status_code=307)