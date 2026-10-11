from jose import jwt,JWTError
from passlib.context import CryptContext
from datetime import datetime,timedelta
from fastapi import HTTPException,status
import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM=os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))


#password hashing
pwt_Context=CryptContext(schemes=["bcrypt"], deprecated="auto")

credentials_exception=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Could not validate credentials",
                                    headers={"WWW-Authenticate":"Bearer"})
#password_hashing
def hash_password(password:str):
    return pwt_Context.hash(password)

#verify password
def verify_password(password:str, hashed_password:str):
    return pwt_Context.verify(password,hashed_password)

#creates access token
def create_access_token(data:dict)-> str:
    encode=data.copy()
    expire=datetime.utcnow()+timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    encode.update({"exp":expire})
    token=jwt.encode(encode,SECRET_KEY,algorithm=ALGORITHM)
    return token


#verify access token
def verify_access_token(token:str)-> dict:
    try:
       payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

       return payload
    except JWTError:
        return credentials_exception