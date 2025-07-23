from fastapi import FastAPI, Depends, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional

from sqlalchemy.orm import Session

from .database import get_db, Base, engine
from .models import User, Profile, Job, Application, UserRole
from .schemas import UserCreate, UserOut, Token
from .auth import get_password_hash, verify_password, create_access_token, get_current_user

from pydantic import BaseModel, Field

app = FastAPI(
    title="IT Job Portal API",
    description="Backend for IT Job Portal, supporting registration, login, and job/application management.",
    version="0.1.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and registration"},
        {"name": "profile", "description": "User profile management"},
        {"name": "jobs", "description": "Job CRUD and listing"},
        {"name": "applications", "description": "Job applications"},
        {"name": "health", "description": "Health check"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables if DB does not exist (for development)
Base.metadata.create_all(bind=engine)

@app.get("/", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}

# --- Schemas required for profile, jobs, applications API ---

class ProfileOut(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str]
    bio: Optional[str]
    skills: Optional[str]
    company: Optional[str]
    class Config:
        orm_mode = True

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, description="Full name")
    bio: Optional[str] = Field(None, description="Short bio")
    skills: Optional[str] = Field(None, description="Skills (comma-separated)")
    company: Optional[str] = Field(None, description="Company (if employer)")

class JobBase(BaseModel):
    title: str = Field(..., description="Job title")
    description: str = Field(..., description="Job description")
    location: Optional[str] = Field(None, description="Location")

class JobCreate(JobBase):
    pass

class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None

class JobOut(JobBase):
    id: int
    created_at: str
    employer_id: int
    employer_name: Optional[str] = None
    class Config:
        orm_mode = True

class ApplicationBase(BaseModel):
    cover_letter: Optional[str] = Field(None, description="Optional cover letter")

class ApplicationCreate(ApplicationBase):
    job_id: int

class ApplicationOut(ApplicationBase):
    id: int
    job_id: int
    user_id: int
    status: str
    applied_at: str
    job: Optional[JobOut]
    user_email: Optional[str]
    class Config:
        orm_mode = True

# --- Helper functions for role-based checks ---

def require_role(user: User, role: str):
    if user.role.value != role:
        raise HTTPException(status_code=403, detail=f"Action allowed only for {role}s.")

# ========== AUTH (Register/Login) ==========

# PUBLIC_INTERFACE
@app.post("/auth/register", response_model=UserOut, status_code=201, tags=["auth"],
          summary="Register a new user",
          description="Register as job seeker or employer. Email must be unique.")
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user (employer or job seeker). The email must be unique.

    Args:
        user_in (UserCreate): Registration info (email, password, role).
        db (Session): SQLAlchemy session (injected).

    Returns:
        UserOut: Created user object, excluding password.
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
    hashed = get_password_hash(user_in.password)
    user = User(email=user_in.email, hashed_password=hashed, role=user_in.role)
    db.add(user)
    db.flush()
    # Create profile slot too
    db.add(Profile(user=user))
    db.commit()
    db.refresh(user)
    return user

# PUBLIC_INTERFACE
@app.post("/auth/login", response_model=Token, tags=["auth"],
          summary="Login (get JWT)",
          description="Authenticate with email and password to receive a JWT access token.")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login a user and return a JWT access token.
    Uses form data, expects username -> email and password.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(data={
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    })
    return Token(access_token=access_token)

# ========== PROFILE (separate table) ==========

# PUBLIC_INTERFACE
@app.get("/profile", response_model=ProfileOut, tags=["profile"],
         summary="Get your profile",
         description="Get the profile of the logged in user.")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    return prof

# PUBLIC_INTERFACE
@app.put("/profile", response_model=ProfileOut, tags=["profile"],
         summary="Update your profile",
         description="Update profile details for logged in user (job seeker or employer).")
def update_profile(profile_in: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prof = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    for k, v in profile_in.model_dump(exclude_unset=True).items():
        setattr(prof, k, v)
    db.commit()
    db.refresh(prof)
    return prof

# ========== JOBS (CRUD for employer, listing/filtering/detail for seekers) ==========

# PUBLIC_INTERFACE
@app.post("/jobs", response_model=JobOut, tags=["jobs"],
         summary="Create a new job (employer only)",
         description="Employers can create jobs.")
def create_job(job_in: JobCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "employer")
    job = Job(**job_in.model_dump(), employer_id=current_user.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobOut(id=job.id, title=job.title, description=job.description, location=job.location, created_at=str(job.created_at), employer_id=job.employer_id, employer_name=current_user.profile.company if current_user.profile else None)

# PUBLIC_INTERFACE
@app.get("/jobs", response_model=List[JobOut], tags=["jobs"],
         summary="List/filter/search jobs",
         description="Anyone can list jobs. Search is by title, location or employer's company.")
def list_jobs(
    search: Optional[str] = Query(None, description="Search term for job title or description"),
    location: Optional[str] = Query(None, description="Location"),
    db: Session = Depends(get_db)
):
    q = db.query(Job)
    if search:
        q = q.filter((Job.title.ilike(f"%{search}%")) | (Job.description.ilike(f"%{search}%")))
    if location:
        q = q.filter(Job.location.ilike(f"%{location}%"))
    jobs = q.order_by(Job.created_at.desc()).all()
    out = []
    for job in jobs:
        employer_name = job.employer.profile.company if job.employer and job.employer.profile and job.employer.profile.company else None
        out.append(JobOut(
            id=job.id,
            title=job.title,
            description=job.description,
            location=job.location,
            created_at=str(job.created_at),
            employer_id=job.employer_id,
            employer_name=employer_name
        ))
    return out

# PUBLIC_INTERFACE
@app.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"],
         summary="Get job detail",
         description="Anyone can view job detail.")
def get_job(job_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    employer_name = job.employer.profile.company if job.employer and job.employer.profile else None
    return JobOut(
        id=job.id,
        title=job.title,
        description=job.description,
        location=job.location,
        created_at=str(job.created_at),
        employer_id=job.employer_id,
        employer_name=employer_name
    )

# PUBLIC_INTERFACE
@app.put("/jobs/{job_id}", response_model=JobOut, tags=["jobs"],
         summary="Update a job (employer only, must own job)",
         description="Employer can update a job posting they own.")
def update_job(job_id: int, job_in: JobUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "employer")
    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    for k, v in job_in.model_dump(exclude_unset=True).items():
        setattr(job, k, v)
    db.commit()
    db.refresh(job)
    employer_name = current_user.profile.company if current_user.profile else None
    return JobOut(id=job.id, title=job.title, description=job.description, location=job.location, created_at=str(job.created_at), employer_id=job.employer_id, employer_name=employer_name)

# PUBLIC_INTERFACE
@app.delete("/jobs/{job_id}", status_code=204, tags=["jobs"],
         summary="Delete a job (employer only, must own job)",
         description="Employer can delete a job posting they own.")
def delete_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "employer")
    job = db.query(Job).filter(Job.id == job_id, Job.employer_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    db.delete(job)
    db.commit()
    return

# ========== APPLICATIONS (seekers apply, employer review) ==========

# PUBLIC_INTERFACE
@app.post("/applications", response_model=ApplicationOut, status_code=201, tags=["applications"],
        summary="Apply for a job (job seeker only)",
        description="Job seeker can apply for a job. Can't apply twice.")
def apply_job(app_in: ApplicationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "seeker")
    job = db.query(Job).filter(Job.id == app_in.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    existing = db.query(Application).filter(Application.job_id == app_in.job_id, Application.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already applied to this job")
    app = Application(job_id=app_in.job_id, user_id=current_user.id, cover_letter=app_in.cover_letter)
    db.add(app)
    db.commit()
    db.refresh(app)
    return ApplicationOut(
        id=app.id, job_id=app.job_id, user_id=app.user_id,
        cover_letter=app.cover_letter, status=app.status, applied_at=str(app.applied_at),
        job=None, user_email=current_user.email
    )

# PUBLIC_INTERFACE
@app.get("/applications", response_model=List[ApplicationOut], tags=["applications"],
        summary="List job applications (user: sees own apps; employer: sees applicants for their jobs)",
        description="Job seeker: list your applications. Employer: all applicants to your jobs.")
def list_applications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == UserRole.seeker:
        # Seeker: list own
        apps = db.query(Application).filter(Application.user_id == current_user.id).all()
    elif current_user.role == UserRole.employer:
        # Employer: all apps to their jobs
        job_ids = [j.id for j in db.query(Job).filter(Job.employer_id == current_user.id).all()]
        apps = db.query(Application).filter(Application.job_id.in_(job_ids)).all() if job_ids else []
    else:
        raise HTTPException(status_code=400, detail="Invalid role.")
    out = []
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        out.append(ApplicationOut(
            id=app.id,
            job_id=app.job_id,
            user_id=app.user_id,
            cover_letter=app.cover_letter,
            status=app.status,
            applied_at=str(app.applied_at),
            job=JobOut(
                id=job.id, title=job.title, description=job.description,
                location=job.location, created_at=str(job.created_at),
                employer_id=job.employer_id, employer_name=(job.employer.profile.company if job.employer and job.employer.profile else None)
            ) if job else None,
            user_email=db.query(User).filter(User.id == app.user_id).first().email
        ))
    return out

# PUBLIC_INTERFACE
@app.put("/applications/{application_id}", response_model=ApplicationOut, tags=["applications"],
        summary="Update application status (employer only)",
        description="Employer can mark an application as reviewed/rejected/hired for jobs they own.")
def update_application_status(application_id: int, status_in: str = Query(..., description="New status (reviewed/rejected/hired)"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(current_user, "employer")
    app = db.query(Application).join(Job).filter(Application.id == application_id, Job.employer_id == current_user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not authorized")
    if status_in not in ["reviewed", "rejected", "hired"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    app.status = status_in
    db.commit()
    db.refresh(app)
    job = db.query(Job).filter(Job.id == app.job_id).first()
    return ApplicationOut(
        id=app.id,
        job_id=app.job_id,
        user_id=app.user_id,
        cover_letter=app.cover_letter,
        status=app.status,
        applied_at=str(app.applied_at),
        job=JobOut(
            id=job.id, title=job.title, description=job.description,
            location=job.location, created_at=str(job.created_at),
            employer_id=job.employer_id, employer_name=(job.employer.profile.company if job.employer and job.employer.profile else None)
        ) if job else None,
        user_email=db.query(User).filter(User.id == app.user_id).first().email
    )

# Note: OpenAPI docs available at /docs or /redoc.

