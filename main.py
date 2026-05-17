<<<<<<< HEAD
# =============================================================================
# IMPORTS
# =============================================================================

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_FILE = BASE_DIR / "job_dataset.json"

# Replace with your API key
load_dotenv()
import os

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

FRONTEND_URL = "http://localhost:3000"

TOP_K_RESULTS = 5
MAX_RESUME_LENGTH = 10000

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# =============================================================================
# GEMINI CONFIGURATION
# =============================================================================

genai.configure(
    api_key=GEMINI_API_KEY
)

# =============================================================================
# RATE LIMITER
# =============================================================================

limiter = Limiter(
    key_func=get_remote_address
)

# =============================================================================
# GLOBAL MEMORY
# =============================================================================

jobs_data = []

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RecommendRequest(BaseModel):

    resume_text: str = Field(
        ...,
        min_length=10
    )

    @field_validator("resume_text")
    @classmethod
    def validate_resume(
        cls,
        value: str
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "resume_text cannot be empty"
            )

        if len(value) > MAX_RESUME_LENGTH:
            raise ValueError(
                f"resume_text exceeds "
                f"{MAX_RESUME_LENGTH} characters"
            )

        return value


class RefineRequest(BaseModel):

    resume_text: str
    user_feedback: str


class CandidateInfo(BaseModel):

    name: str
    skills: list[str]
    experience_years: int
    preferred_roles: list[str]
    education: str


class RankedJob(BaseModel):

    id: int
    title: str
    company: str
    similarity_score: float
    explanation: str


class RecommendResponse(BaseModel):

    candidate: CandidateInfo
    ranked_jobs: list[RankedJob]
    clarifying_question: str

# =============================================================================
# GEMINI RESPONSE HELPER
# =============================================================================

def generate_json_response(
    prompt: str
) -> dict:

    logger.info(
        "Calling Gemini API"
    )

    try:

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        response = model.generate_content(
            prompt
        )

        text = response.text.strip()

        print("\n=== GEMINI RAW RESPONSE ===")
        print(text)
        print("===========================\n")

        # Remove markdown formatting
        if text.startswith("```"):

            text = (
                text.replace(
                    "```json",
                    ""
                )
                .replace(
                    "```",
                    ""
                )
                .strip()
            )

        try:
            return json.loads(text)

        except Exception:

            return {
                "raw_response": text
            }

    except Exception as e:

        logger.exception(
            "Gemini API failed"
        )

        return {
            "error": str(e)
        }

# =============================================================================
# LOAD DATASET
# =============================================================================

def load_jobs() -> None:

    global jobs_data

    logger.info(
        "Loading job dataset"
    )

    with open(
        DATASET_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        jobs_data = json.load(file)

    logger.info(
        f"Loaded {len(jobs_data)} jobs"
    )

# =============================================================================
# AI JOB RANKING
# =============================================================================

def rank_jobs_with_gemini(
    resume_text: str
) -> list[dict]:

    logger.info(
        "Ranking jobs with Gemini"
    )

    # Simple keyword matching fallback
    matched_jobs = []

    resume_lower = resume_text.lower()

    for job in jobs_data:

        score = 0

        title = str(
            job.get("title", "")
        ).lower()

        description = str(
            job.get("description", "")
        ).lower()

        skills = " ".join(
            job.get("skills", [])
        ).lower()

        # Simple keyword scoring
        for keyword in resume_lower.split():

            if keyword in title:
                score += 3

            if keyword in description:
                score += 2

            if keyword in skills:
                score += 5

        matched_jobs.append({
            "id": job["id"],
            "title": job.get(
                "title",
                "Unknown"
            ),
            "company": job.get(
                "company",
                "Unknown"
            ),
            "similarity_score":
                round(score / 10, 2),
            "explanation":
                "Matched based on skills and keywords"
        })

    matched_jobs.sort(
        key=lambda x:
            x["similarity_score"],
        reverse=True
    )

    return matched_jobs[:5]
    

    response = generate_json_response(
        prompt
    )

    print(response)

    if "ranked_jobs" not in response:

        return []

    ranked_jobs = []

    for item in response["ranked_jobs"]:

        matched_job = next(
            (
                job for job in jobs_data
                if job["id"] == item["id"]
            ),
            None
        )

        if matched_job:

            ranked_jobs.append({
                "id": matched_job["id"],
                "title": matched_job.get(
                    "title",
                    "Unknown"
                ),
                "company": matched_job.get(
                    "company",
                    "Unknown"
                ),
                "similarity_score": 0.95,
                "explanation": item.get(
                    "reason",
                    "No explanation"
                )
            })

    logger.info(
        "AI ranking completed"
    )

    return ranked_jobs[:TOP_K_RESULTS]

# =============================================================================
# CANDIDATE EXTRACTION
# =============================================================================

def extract_candidate_information(
    resume_text: str
) -> dict:

    skills = []

    known_skills = [
        "python",
        "fastapi",
        "machine learning",
        "deep learning",
        "nlp",
        "sql",
        "tensorflow",
        "pytorch",
        "javascript",
        "react",
        "node",
        "docker",
        "aws",
        "langchain"
    ]

    resume_lower = resume_text.lower()

    for skill in known_skills:

        if skill in resume_lower:
            skills.append(skill)

    return {
        "name": "Candidate",
        "skills": skills,
        "experience_years": 1,
        "preferred_roles": [
            "Software Engineer",
            "ML Engineer"
        ],
        "education": "Not Specified"
    }

    response = generate_json_response(
        prompt
    )

    if "name" not in response:

        return {
            "name": "Unknown",
            "skills": [],
            "experience_years": 0,
            "preferred_roles": [],
            "education": "Unknown"
        }

    return response

# =============================================================================
# AI REASONING ENGINE
# =============================================================================

def generate_reasoning(
    candidate: dict,
    jobs: list[dict]
) -> dict:

    logger.info(
        "Generating reasoning"
    )

    prompt = f"""
    Candidate:
    {json.dumps(candidate, indent=2)}

    Recommended Jobs:
    {json.dumps(jobs, indent=2)}

    Explain why each job fits.

    Return STRICT JSON ONLY.

    Schema:

    {{
      "reasoned_jobs": [
        {{
          "id": 1,
          "explanation": "string"
        }}
      ],
      "clarifying_question": "string"
    }}
    """

    response = generate_json_response(
        prompt
    )

    if "reasoned_jobs" not in response:

        return {
            "reasoned_jobs": [],
            "clarifying_question":
                "What type of role are you looking for?"
        }

    return response
# =============================================================================
# RECOMMENDATION PIPELINE
# =============================================================================

def generate_recommendations(
    resume_text: str
) -> dict:

    logger.info(
        "Generating recommendations"
    )

    # ---------------------------------
    # Step 1: Rank Jobs
    # ---------------------------------

    top_jobs = (
        rank_jobs_with_gemini(
            resume_text
        )
    )

    # ---------------------------------
    # Step 2: Extract Candidate
    # ---------------------------------

    candidate = (
        extract_candidate_information(
            resume_text
        )
    )

    # ---------------------------------
    # Step 3: Generate Reasoning
    # ---------------------------------

    reasoning = (
        generate_reasoning(
            candidate,
            top_jobs
        )
    )

    # ---------------------------------
    # Step 4: Build Explanation Map
    # ---------------------------------

    explanation_map = {
        item["id"]: item["explanation"]
        for item in reasoning.get(
            "reasoned_jobs",
            []
        )
    }

    # ---------------------------------
    # Step 5: Final Ranked Jobs
    # ---------------------------------

    ranked_jobs = []

    for job in top_jobs:

        ranked_jobs.append({
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "similarity_score":
                job["similarity_score"],
            "explanation":
                explanation_map.get(
                    job["id"],
                    job["explanation"]
                )
        })

    logger.info(
        "Recommendations completed"
    )

    return {
        "candidate": candidate,
        "ranked_jobs": ranked_jobs,
        "clarifying_question":
            reasoning.get(
                "clarifying_question",
                "What type of role are you looking for?"
            )
    }

# =============================================================================
# REFINEMENT ENGINE
# =============================================================================

def refine_recommendations(
    resume_text: str,
    user_feedback: str
) -> dict:

    logger.info(
        "Refining recommendations"
    )

    prompt = f"""
    Resume:
    {resume_text}

    User Feedback:
    {user_feedback}

    Refine candidate preferences.

    Return STRICT JSON ONLY.

    Schema:

    {{
      "updated_preferences": [
        "string"
      ],
      "notes": "string"
    }}
    """

    response = generate_json_response(
        prompt
    )

    if "updated_preferences" not in response:

        return {
            "updated_preferences": [],
            "notes": "No refinement generated"
        }

    return response

# =============================================================================
# ASYNC HELPERS
# =============================================================================

async def async_generate_recommendations(
    resume_text: str
) -> dict:

    return await asyncio.to_thread(
        generate_recommendations,
        resume_text
    )


async def async_refine_recommendations(
    resume_text: str,
    user_feedback: str
) -> dict:

    return await asyncio.to_thread(
        refine_recommendations,
        resume_text,
        user_feedback
    )

# =============================================================================
# FASTAPI LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "Application startup initiated"
    )

    load_jobs()

    logger.info(
        "Application startup completed"
    )

    yield

    logger.info(
        "Application shutdown"
    )

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    
    title="Smart Job Match API",
    description=(
        "AI-powered job recommendation system"
    ),
    version="2.0.0",
    lifespan=lifespan
)
# =============================================================================
# TEMPLATES
# =============================================================================

templates = Jinja2Templates(
    directory="templates"
)

# =============================================================================
# STATIC FILES
# =============================================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
# =============================================================================
# RATE LIMITING
# =============================================================================

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# =============================================================================
# CORS
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# GLOBAL ERROR HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception(
        "Unhandled server exception"
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc)
        }
    )

# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home(
    request: Request
):

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request
        }
    )
# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

@app.get("/health")
async def health_check():

    return {
        "status": "ok",
        "jobs_loaded":
            len(jobs_data),
        "gemini_configured":
            bool(GEMINI_API_KEY)
    }

# =============================================================================
# JOBS ENDPOINT
# =============================================================================

@app.get("/jobs")
async def get_jobs():

    return {
        "total_jobs":
            len(jobs_data),
        "jobs":
            jobs_data[:10]
    }

# =============================================================================
# RECOMMEND ENDPOINT
# =============================================================================

@app.post(
    "/recommend",
    response_model=RecommendResponse
)
@limiter.limit("10/minute")
async def recommend_jobs(
    request: Request,
    payload: RecommendRequest
):

    logger.info(
        "Recommendation request received"
    )

    result = (
        await async_generate_recommendations(
            payload.resume_text
        )
    )

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2))
    print("====================\n")

    return result

# =============================================================================
# REFINE ENDPOINT
# =============================================================================

@app.post("/refine")
@limiter.limit("10/minute")
async def refine_jobs(
    request: Request,
    payload: RefineRequest
):

    logger.info(
        "Refinement request received"
    )

    result = (
        await async_refine_recommendations(
            payload.resume_text,
            payload.user_feedback
        )
    )

    return result

# =============================================================================
# DEBUG ENDPOINT
# =============================================================================

@app.get("/debug")
async def debug():

    return {
        "dataset_loaded":
            len(jobs_data),
        "sample_job":
            jobs_data[0]
            if jobs_data
            else None
    }

# =============================================================================
# VERCEL HANDLER
# =============================================================================

handler = app

# =============================================================================
# LOCAL DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
=======
# =============================================================================
# IMPORTS
# =============================================================================

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import google.generativeai as genai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_FILE = BASE_DIR / "job_dataset.json"

# Replace with your API key
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

FRONTEND_URL = "http://localhost:3000"

TOP_K_RESULTS = 5
MAX_RESUME_LENGTH = 10000

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# =============================================================================
# GEMINI CONFIGURATION
# =============================================================================

genai.configure(
    api_key=GEMINI_API_KEY
)

# =============================================================================
# RATE LIMITER
# =============================================================================

limiter = Limiter(
    key_func=get_remote_address
)

# =============================================================================
# GLOBAL MEMORY
# =============================================================================

jobs_data = []

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RecommendRequest(BaseModel):

    resume_text: str = Field(
        ...,
        min_length=10
    )

    @field_validator("resume_text")
    @classmethod
    def validate_resume(
        cls,
        value: str
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "resume_text cannot be empty"
            )

        if len(value) > MAX_RESUME_LENGTH:
            raise ValueError(
                f"resume_text exceeds "
                f"{MAX_RESUME_LENGTH} characters"
            )

        return value


class RefineRequest(BaseModel):

    resume_text: str
    user_feedback: str


class CandidateInfo(BaseModel):

    name: str
    skills: list[str]
    experience_years: int
    preferred_roles: list[str]
    education: str


class RankedJob(BaseModel):

    id: int
    title: str
    company: str
    similarity_score: float
    explanation: str


class RecommendResponse(BaseModel):

    candidate: CandidateInfo
    ranked_jobs: list[RankedJob]
    clarifying_question: str

# =============================================================================
# GEMINI RESPONSE HELPER
# =============================================================================

def generate_json_response(
    prompt: str
) -> dict:

    logger.info(
        "Calling Gemini API"
    )

    try:

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        response = model.generate_content(
            prompt
        )

        text = response.text.strip()

        print("\n=== GEMINI RAW RESPONSE ===")
        print(text)
        print("===========================\n")

        # Remove markdown formatting
        if text.startswith("```"):

            text = (
                text.replace(
                    "```json",
                    ""
                )
                .replace(
                    "```",
                    ""
                )
                .strip()
            )

        try:
            return json.loads(text)

        except Exception:

            return {
                "raw_response": text
            }

    except Exception as e:

        logger.exception(
            "Gemini API failed"
        )

        return {
            "error": str(e)
        }

# =============================================================================
# LOAD DATASET
# =============================================================================

def load_jobs() -> None:

    global jobs_data

    logger.info(
        "Loading job dataset"
    )

    with open(
        DATASET_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        jobs_data = json.load(file)

    logger.info(
        f"Loaded {len(jobs_data)} jobs"
    )

# =============================================================================
# AI JOB RANKING
# =============================================================================

def rank_jobs_with_gemini(
    resume_text: str
) -> list[dict]:

    logger.info(
        "Ranking jobs with Gemini"
    )

    # Simple keyword matching fallback
    matched_jobs = []

    resume_lower = resume_text.lower()

    for job in jobs_data:

        score = 0

        title = str(
            job.get("title", "")
        ).lower()

        description = str(
            job.get("description", "")
        ).lower()

        skills = " ".join(
            job.get("skills", [])
        ).lower()

        # Simple keyword scoring
        for keyword in resume_lower.split():

            if keyword in title:
                score += 3

            if keyword in description:
                score += 2

            if keyword in skills:
                score += 5

        matched_jobs.append({
            "id": job["id"],
            "title": job.get(
                "title",
                "Unknown"
            ),
            "company": job.get(
                "company",
                "Unknown"
            ),
            "similarity_score":
                round(score / 10, 2),
            "explanation":
                "Matched based on skills and keywords"
        })

    matched_jobs.sort(
        key=lambda x:
            x["similarity_score"],
        reverse=True
    )

    return matched_jobs[:5]
    

    response = generate_json_response(
        prompt
    )

    print(response)

    if "ranked_jobs" not in response:

        return []

    ranked_jobs = []

    for item in response["ranked_jobs"]:

        matched_job = next(
            (
                job for job in jobs_data
                if job["id"] == item["id"]
            ),
            None
        )

        if matched_job:

            ranked_jobs.append({
                "id": matched_job["id"],
                "title": matched_job.get(
                    "title",
                    "Unknown"
                ),
                "company": matched_job.get(
                    "company",
                    "Unknown"
                ),
                "similarity_score": 0.95,
                "explanation": item.get(
                    "reason",
                    "No explanation"
                )
            })

    logger.info(
        "AI ranking completed"
    )

    return ranked_jobs[:TOP_K_RESULTS]

# =============================================================================
# CANDIDATE EXTRACTION
# =============================================================================

def extract_candidate_information(
    resume_text: str
) -> dict:

    skills = []

    known_skills = [
        "python",
        "fastapi",
        "machine learning",
        "deep learning",
        "nlp",
        "sql",
        "tensorflow",
        "pytorch",
        "javascript",
        "react",
        "node",
        "docker",
        "aws",
        "langchain"
    ]

    resume_lower = resume_text.lower()

    for skill in known_skills:

        if skill in resume_lower:
            skills.append(skill)

    return {
        "name": "Candidate",
        "skills": skills,
        "experience_years": 1,
        "preferred_roles": [
            "Software Engineer",
            "ML Engineer"
        ],
        "education": "Not Specified"
    }

    response = generate_json_response(
        prompt
    )

    if "name" not in response:

        return {
            "name": "Unknown",
            "skills": [],
            "experience_years": 0,
            "preferred_roles": [],
            "education": "Unknown"
        }

    return response

# =============================================================================
# AI REASONING ENGINE
# =============================================================================

def generate_reasoning(
    candidate: dict,
    jobs: list[dict]
) -> dict:

    logger.info(
        "Generating reasoning"
    )

    prompt = f"""
    Candidate:
    {json.dumps(candidate, indent=2)}

    Recommended Jobs:
    {json.dumps(jobs, indent=2)}

    Explain why each job fits.

    Return STRICT JSON ONLY.

    Schema:

    {{
      "reasoned_jobs": [
        {{
          "id": 1,
          "explanation": "string"
        }}
      ],
      "clarifying_question": "string"
    }}
    """

    response = generate_json_response(
        prompt
    )

    if "reasoned_jobs" not in response:

        return {
            "reasoned_jobs": [],
            "clarifying_question":
                "What type of role are you looking for?"
        }

    return response
# =============================================================================
# RECOMMENDATION PIPELINE
# =============================================================================

def generate_recommendations(
    resume_text: str
) -> dict:

    logger.info(
        "Generating recommendations"
    )

    # ---------------------------------
    # Step 1: Rank Jobs
    # ---------------------------------

    top_jobs = (
        rank_jobs_with_gemini(
            resume_text
        )
    )

    # ---------------------------------
    # Step 2: Extract Candidate
    # ---------------------------------

    candidate = (
        extract_candidate_information(
            resume_text
        )
    )

    # ---------------------------------
    # Step 3: Generate Reasoning
    # ---------------------------------

    reasoning = (
        generate_reasoning(
            candidate,
            top_jobs
        )
    )

    # ---------------------------------
    # Step 4: Build Explanation Map
    # ---------------------------------

    explanation_map = {
        item["id"]: item["explanation"]
        for item in reasoning.get(
            "reasoned_jobs",
            []
        )
    }

    # ---------------------------------
    # Step 5: Final Ranked Jobs
    # ---------------------------------

    ranked_jobs = []

    for job in top_jobs:

        ranked_jobs.append({
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "similarity_score":
                job["similarity_score"],
            "explanation":
                explanation_map.get(
                    job["id"],
                    job["explanation"]
                )
        })

    logger.info(
        "Recommendations completed"
    )

    return {
        "candidate": candidate,
        "ranked_jobs": ranked_jobs,
        "clarifying_question":
            reasoning.get(
                "clarifying_question",
                "What type of role are you looking for?"
            )
    }

# =============================================================================
# REFINEMENT ENGINE
# =============================================================================

def refine_recommendations(
    resume_text: str,
    user_feedback: str
) -> dict:

    logger.info(
        "Refining recommendations"
    )

    prompt = f"""
    Resume:
    {resume_text}

    User Feedback:
    {user_feedback}

    Refine candidate preferences.

    Return STRICT JSON ONLY.

    Schema:

    {{
      "updated_preferences": [
        "string"
      ],
      "notes": "string"
    }}
    """

    response = generate_json_response(
        prompt
    )

    if "updated_preferences" not in response:

        return {
            "updated_preferences": [],
            "notes": "No refinement generated"
        }

    return response

# =============================================================================
# ASYNC HELPERS
# =============================================================================

async def async_generate_recommendations(
    resume_text: str
) -> dict:

    return await asyncio.to_thread(
        generate_recommendations,
        resume_text
    )


async def async_refine_recommendations(
    resume_text: str,
    user_feedback: str
) -> dict:

    return await asyncio.to_thread(
        refine_recommendations,
        resume_text,
        user_feedback
    )

# =============================================================================
# FASTAPI LIFESPAN
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "Application startup initiated"
    )

    load_jobs()

    logger.info(
        "Application startup completed"
    )

    yield

    logger.info(
        "Application shutdown"
    )

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    
    title="Smart Job Match API",
    description=(
        "AI-powered job recommendation system"
    ),
    version="2.0.0",
    lifespan=lifespan
)
# =============================================================================
# TEMPLATES
# =============================================================================

templates = Jinja2Templates(
    directory="templates"
)

# =============================================================================
# STATIC FILES
# =============================================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
# =============================================================================
# RATE LIMITING
# =============================================================================

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

# =============================================================================
# CORS
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# GLOBAL ERROR HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception(
        "Unhandled server exception"
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc)
        }
    )

# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
async def home(
    request: Request
):

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request
        }
    )
# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

@app.get("/health")
async def health_check():

    return {
        "status": "ok",
        "jobs_loaded":
            len(jobs_data),
        "gemini_configured":
            bool(GEMINI_API_KEY)
    }

# =============================================================================
# JOBS ENDPOINT
# =============================================================================

@app.get("/jobs")
async def get_jobs():

    return {
        "total_jobs":
            len(jobs_data),
        "jobs":
            jobs_data[:10]
    }

# =============================================================================
# RECOMMEND ENDPOINT
# =============================================================================

@app.post(
    "/recommend",
    response_model=RecommendResponse
)
@limiter.limit("10/minute")
async def recommend_jobs(
    request: Request,
    payload: RecommendRequest
):

    logger.info(
        "Recommendation request received"
    )

    result = (
        await async_generate_recommendations(
            payload.resume_text
        )
    )

    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2))
    print("====================\n")

    return result

# =============================================================================
# REFINE ENDPOINT
# =============================================================================

@app.post("/refine")
@limiter.limit("10/minute")
async def refine_jobs(
    request: Request,
    payload: RefineRequest
):

    logger.info(
        "Refinement request received"
    )

    result = (
        await async_refine_recommendations(
            payload.resume_text,
            payload.user_feedback
        )
    )

    return result

# =============================================================================
# DEBUG ENDPOINT
# =============================================================================

@app.get("/debug")
async def debug():

    return {
        "dataset_loaded":
            len(jobs_data),
        "sample_job":
            jobs_data[0]
            if jobs_data
            else None
    }

# =============================================================================
# VERCEL HANDLER
# =============================================================================

handler = app

# =============================================================================
# LOCAL DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
>>>>>>> 08620d642400fd3f97331b715acd5fc605201f9e
    )