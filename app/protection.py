from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends,HTTPException,status
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_access_token,credentials_exception
from models import User
from schema import UserRole
import models

OAuth_Schema=OAuth2PasswordBearer('auth/login')

def get_current_user(token:str=Depends(OAuth_Schema),
                     db:Session=Depends(get_db)):

   

    #verify the token and get the payload
    payload=verify_access_token(token)

    #from payload get the user id 
    user_id=payload.get("sub")

    #verify id
    if user_id is None:
        raise credentials_exception

    #get user from database & verify if user exists
    user=db.query(models.User).filter(models.User.id==user_id).first()

    if user is None:
        raise credentials_exception

    return user
