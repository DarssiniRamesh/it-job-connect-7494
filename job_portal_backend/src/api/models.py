from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .database import Base

class UserRole(str, enum.Enum):
    employer = "employer"
    seeker = "seeker"

class User(Base):
    """User account (can be employer or job seeker)."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)

    profile = relationship("Profile", back_populates="user", uselist=False)
    jobs = relationship("Job", back_populates="employer", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")

class Profile(Base):
    """Profile for job seeker or employer, linked to a user."""
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)   # comma-separated for simplicity
    company = Column(String, nullable=True)  # For employer

    user = relationship("User", back_populates="profile")

class Job(Base):
    """Job posting by employer."""
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    employer_id = Column(Integer, ForeignKey("users.id"))  # Only employer users

    employer = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

class Application(Base):
    """Application to a job by a job seeker."""
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    user_id = Column(Integer, ForeignKey("users.id"))  # The job seeker
    cover_letter = Column(Text, nullable=True)
    status = Column(String, default="submitted")  # submitted, reviewed, rejected, hired
    applied_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="applications")
    user = relationship("User", back_populates="applications")
