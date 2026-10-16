from pydantic import BaseModel,EmailStr, HttpUrl,field_validator,model_validator  
from typing import Optinal  


###############################
#LOGIN SCHEMAS

class register(BaseModel):
    name:str
    email:EmailStr
    password:str
    confirm_password:str

    @field_validator("password")
    def validate_password(cls,password):
        if len(password)<8:
            raise ValueError("Password must be at least 8 characters long")
        return password

    
    @field_validator("email")
    def check_company_email(cls, value):
        if value.endswith("@mycompany.com"):
            raise ValueError("Input valid email")
        return value
    
    @model_validator(mode="after")
    def password_verify(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class Userlogin(BaseModel):
     name:str
     email:EmailStr
     password:str

     @field_validator("email")
     def check_company_email(cls, value):
             if value.endswith("@mycompany.com"):
                 raise ValueError("Input valid email")
             return value

    
class URL(BaseModel):
     original_url:HttpUrl
     custom_code:Optinal[str] = None    

     
