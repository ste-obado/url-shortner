from database import  get_db
from sqlalchemy.orm import Session
from fastapi import APIRouter,Depends,HTTPException,status
from protection import get_current_user
from models import URL,Click
from sqlalchemy import func
from util.ratelimiter import rate_limit
from redis_cache import redis_client

router=APIRouter(
    prefix="/stats",
    tags=["Statistics"]
)

@router.get("/stats/{code}")
def get_stats(code:str,db:Session=Depends(get_db),current_user=Depends(get_current_user)):
    url=db.query(URL).filter(URL.code==code).first()
    stats_key=f"stats:{code}"
    GET_STATS=redis_client.get(stats_key)
    
    if GET_STATS:
        return {"Code":code,
                "total_clicks":GET_STATS["total_clicks"],
                "Clicks_per_day":GET_STATS["Clicks_per_day"]}
    
    if url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="URL not found")
    
    if url.owner_id!=current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Not authorized to view stats for this URL")

    
    total_clicks=db.query(Click).filter(Click.url_id==url.id).count()

    clicks_per_day=db.query(Click).filter(Click.url_id==url.id).group_by(func.date(Click.clicked_at)).count()

    redis_client.set(stats_key,{"total_clicks":total_clicks,"Clicks_per_day":clicks_per_day},ex=60*60)  # cache for 1 hour
  
    return {"Code":url.code,
            "total_clicks":total_clicks,
            "Clicks_per_day":clicks_per_day}            

