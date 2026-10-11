from fastapi import FastAPI
from app.routers.auth import auth
from database import Base,engine
import models
from routers import auth,stats,urls
from fastapi import FastAPI


app=FastAPI("URL_SHORTENER")

#CREATE TABLES 
models.Base.metadata.create_all(bind=engine)

#include each router 
app.include_router(auth.router)
app.include_router(stats.router) 
app.include_router(urls.router)