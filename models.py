# models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import ARRAY

Base = declarative_base()

class MasterClass(Base):
    __tablename__ = "master_classes"
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    photo = Column(String, nullable=True)  # путь к фото
    slots = relationship("Slot", back_populates="master_class")
    max_people = Column(Integer, nullable=False)
    is_team = Column(Integer, default=0)  # 0 — обычный, 1 — командный

class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True)
    master_class_id = Column(Integer, ForeignKey("master_classes.id"))
    time = Column(DateTime, nullable=False)
    max_people = Column(Integer, nullable=False)
    registrations = relationship("Registration", back_populates="slot")
    master_class = relationship("MasterClass", back_populates="slots")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    registrations = relationship("Registration", back_populates="user")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    members = Column(ARRAY(String))  # tg_id участников
    registration_id = Column(Integer, ForeignKey("registrations.id"))

class Registration(Base):
    __tablename__ = "registrations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    slot_id = Column(Integer, ForeignKey("slots.id"))
    team = relationship("Team", uselist=False, backref="registration")
    user = relationship("User", back_populates="registrations")
    slot = relationship("Slot", back_populates="registrations")
