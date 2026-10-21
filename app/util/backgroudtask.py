
from models import Click
from database import SessionLocal
import logging


def record_click(short_code: str,user_agent: str,db=SessionLocal()):
    logger = logging.getLogger(__name__)
    add_click=Click(short_code=short_code,user_agent=user_agent)
    try:
        db.add(add_click)
        db.commit()
        logger.info("Click recorded for %s", short_code)
    except:
        db.rollback()
        logger.exception("Failed to record click from code %s", short_code)
    finally:
        db.close()

    

   

