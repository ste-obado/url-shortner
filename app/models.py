from sqlalchemy import Column,Integer,String,Boolean,ForeignKey,DateTime,func
from database import Base
import uuid
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id = Column(str(uuid.uuid4()), primary_key=True,nullable=False)
    email = Column(String, unique=True, index=True,nullable=False)
    hashed_password = Column(String,nullable=False)
    is_active = Column(Boolean, default=True)
    urls = relationship("URL", back_populates="user",cascade="all,delete-orphan")  # Relationship to URL

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"),nullable=False)
    original_url = Column(String, unique=True, nullable=False)
    Code = Column(String, unique=True, nullable=True)
    user = relationship("User", back_populates="urls")
    click=relationship("Click", back_populates="url",cascade="all,delete-orphan")  # Relationship to

class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, nullable=False)
    url_id = Column(Integer, ForeignKey("urls.id"),nullable=False)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now())
    user_agent = Column(String, nullable=True) 
    url = relationship("URL", back_populates="clicks")  # You can use DateTime if you prefer