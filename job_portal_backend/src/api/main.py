from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from .database import get_db, Base, engine
from .models import User
from .schemas import UserCreate, UserOut, Token
from .auth import get_password_hash, verify_password, create_access_token

app = FastAPI(
    title="IT Job Portal API",
    description="Backend for IT Job Portal, supporting registration, login, and job management.",
    version="0.1.0",
    openapi_tags=[
        {"name": "auth", "description": "Authentication and registration"},
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
    db.commit()
    db.refresh(user)
    return user

# PUBLIC_INTERFACE
@app.post("/auth/login", response_model=Token, tags=["auth"],
          summary="Login (get JWT)",
          description="Authenticate with email and password to receive a JWT access token.")
def login_user(form_data: UserCreate = Depends(), db: Session = Depends(get_db)):
    """
    Login a user and return a JWT access token.

    Args:
        form_data (UserCreate): Login info (email, password, role).
        db (Session): SQLAlchemy session (injected).

    Returns:
        Token: JWT token for authenticating requests.
    """
    user = db.query(User).filter(User.email == form_data.email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user.role != form_data.role:
        raise HTTPException(status_code=401, detail="Role mismatch")
    access_token = create_access_token(data={
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value
    })
    return Token(access_token=access_token)
