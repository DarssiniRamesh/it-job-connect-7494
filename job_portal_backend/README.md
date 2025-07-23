# IT Job Portal Backend

A FastAPI-based backend providing RESTful APIs for an IT job portal, supporting user authentication, job postings, application tracking, and profile management for both job seekers and employers.

## Features

- **User registration & login** (job seekers and employers)
- **JWT-based authentication** for secure API access
- **Job posting** (employers)
- **Job seeking** (search, filter, and detail view)
- **Job application** (by job seekers)
- **Application management/tracking** (view, status updates)
- **User profile management** (bio, skills, company)
- **Role-based access** for dashboards and actions
- OpenAPI documentation generated and accessible at `/docs`

## Setup Instructions

### Prerequisites

- Python 3.9+
- pip (Python package manager)
- (Recommended) virtualenv or similar for isolated environment

### Installation

1. **Clone the repository**
   ```sh
   git clone <repo_url>
   cd it-job-connect-7494/job_portal_backend
   ```

2. **(Optional) Create a virtual environment**
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```sh
   pip install -r requirements.txt
   ```

4. **Setup environment variables**

   The backend loads variables from a `.env` file or system environment. The most relevant variables (add them to `.env` in the project root):

   ```
   DATABASE_URL=sqlite:///./job_portal.db
   JWT_SECRET_KEY=your_jwt_secret
   ALEMBIC_DB_URL=sqlite:///./job_portal.db
   ```

   - `DATABASE_URL`: SQLAlchemy connection string (default is local SQLite)
   - `JWT_SECRET_KEY`: Secret key for signing JWT tokens (**change this in production!**)
   - `ALEMBIC_DB_URL`: For migrations (alembic)

5. **Run database migrations (optional for fresh dev, required for production upgrades)**
   ```sh
   alembic upgrade head
   ```

## How to Run Locally

- **Dev mode (with automatic reload):**
  ```sh
  uvicorn src.api.main:app --reload --port 8000
  ```
- Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API docs.

- **Production:** Use `gunicorn`/`uvicorn` or similar process manager.

## API Usage

The backend provides the following core REST endpoints under `http://localhost:8000`:

### Authentication

- **Register**  
  `POST /auth/register`  
  Request JSON: `{ "email": "...", "password": "...", "role": "seeker|employer" }`

- **Login**  
  `POST /auth/login`  
  Request form (`application/x-www-form-urlencoded`): `username`, `password`  
  Response: `{ "access_token": "..." }` (JWT Bearer token)

### Profile

- **Get profile**  
  `GET /profile` (JWT required)

- **Update profile**  
  `PUT /profile` (JWT required)  
  Body: `{ "full_name": "...", "bio": "...", "skills": "...", "company": "..." }`

### Jobs

- **List jobs**  
  `GET /jobs?search=&location=`

- **Job detail**  
  `GET /jobs/{job_id}`

- **Create job** (employer only)  
  `POST /jobs` (JWT required, role: employer)

- **Update/Delete job**  
  `PUT /jobs/{job_id}` / `DELETE /jobs/{job_id}` (JWT/role required, must own job)

### Applications

- **List applications**  
  `GET /applications`  
  - For seekers: returns own applications
  - For employers: returns all to their jobs

- **Apply for job**  
  `POST /applications` (JWT required, role: seeker)  
  Body: `{ "job_id": <int>, "cover_letter": null|text }`

- **Update application status**  
  `PUT /applications/{application_id}?status_in=reviewed|rejected|hired` (JWT required, role: employer)

- See `/docs` for full OpenAPI details.

## Integration Points

The backend is intended to be used with the `job_portal_frontend` React app (see that directory for usage).  
- Supports CORS (all origins in dev)
- Returns standard JSON responses with proper status codes
- JWT tokens are expected in the `Authorization: Bearer <token>` header

## License

MIT (or as provided by this repository)
