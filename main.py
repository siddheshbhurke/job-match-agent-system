# =============================================================================
# IMPORTS
# =============================================================================

import os
import json
import asyncio
import logging

from pathlib import Path
from contextlib import asynccontextmanager

import google.generativeai as genai

from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.responses import (
    JSONResponse,
    HTMLResponse
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pydantic import (
    BaseModel,
    Field,
    field_validator
)

from slowapi import (
    Limiter,
    _rate_limit_exceeded_handler
)

from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# =============================================================================
# CONFIGURATION
# =============================================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATASET_FILE = BASE_DIR / "job_dataset.json"

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

if not GEMINI_API_KEY:

    raise ValueError(
        "GEMINI_API_KEY not found in .env"
    )

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
# GEMINI JSON HELPER
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

        print("\n=== GEMINI RESPONSE ===")
        print(text)
        print("=======================\n")

        # Remove markdown wrappers

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

        except Exception as e:

            print("\n=== JSON PARSE ERROR ===")
            print(text)
            print("========================\n")

            logger.exception(
                "Invalid JSON returned by Gemini"
            )

            return {
                "error": str(e),
                "raw_response": text
            }

    except Exception as e:

        logger.exception(
            "Gemini API failure"
        )

        return {
            "error": str(e)
        }


# =============================================================================
# LOAD JOB DATASET
# =============================================================================

def load_jobs() -> None:

    global jobs_data

    logger.info(
        "Loading job dataset"
    )

    if not DATASET_FILE.exists():

        raise FileNotFoundError(
            "job_dataset.json not found"
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
# CANDIDATE EXTRACTION
# =============================================================================

def extract_candidate_information(
    resume_text: str
) -> dict:

    logger.info(
        "Extracting candidate information"
    )

    prompt = f"""
    Extract structured candidate information
    from this resume.

    Resume:
    {resume_text}

    Return STRICT JSON ONLY.

    Schema:

    {{
      "name": "string",
      "skills": ["string"],
      "experience_years": 0,
      "preferred_roles": ["string"],
      "education": "string"
    }}
    """

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
# INITIAL JOB RANKING
# =============================================================================

def rank_jobs(
    resume_text: str
) -> list[dict]:

    logger.info(
        "Generating initial rankings"
    )

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

        for keyword in resume_lower.split():

            if keyword in title:
                score += 3

            if keyword in description:
                score += 2

            if keyword in skills:
                score += 5

        matched_jobs.append({

            "id": job.get("id"),

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
                "Matched based on resume relevance"
        })

    matched_jobs.sort(
        key=lambda x:
            x["similarity_score"],
        reverse=True
    )

    return matched_jobs[:TOP_K_RESULTS]


# =============================================================================
# AI REASONING + DYNAMIC QUESTION
# =============================================================================

def generate_reasoning(
    candidate: dict,
    jobs: list[dict]
) -> dict:

    logger.info(
        "Generating reasoning"
    )

    prompt = f"""
    You are an AI hiring assistant.

    Candidate Profile:
    {json.dumps(candidate, indent=2)}

    Top Matched Jobs:
    {json.dumps(jobs, indent=2)}

    Tasks:

    1. Explain why each job matches.
    2. Generate ONE highly specific
       clarifying question.

    IMPORTANT RULES:

    - The question MUST depend on:
      - the resume
      - matched jobs

    - The question MUST help improve
      ranking accuracy.

    - The question MUST NOT be generic.

    BAD EXAMPLES:
    - Tell me more about yourself
    - What kind of role do you want

    GOOD EXAMPLES:
    - backend vs AI engineering
    - research vs production
    - startup vs enterprise
    - remote vs onsite
    - deployment vs modeling

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
                "Would you prefer AI-focused "
                "roles or backend engineering roles?"
        }

    return response


# =============================================================================
# MAIN RECOMMENDATION PIPELINE
# =============================================================================

def generate_recommendations(
    resume_text: str
) -> dict:

    logger.info(
        "Generating recommendations"
    )

    # ---------------------------------
    # Step 1: Initial Ranking
    # ---------------------------------

    top_jobs = rank_jobs(
        resume_text
    )

    # ---------------------------------
    # Step 2: Candidate Extraction
    # ---------------------------------

    candidate = extract_candidate_information(
        resume_text
    )

    # ---------------------------------
    # Step 3: AI Reasoning
    # ---------------------------------

    reasoning = generate_reasoning(
        candidate,
        top_jobs
    )

    explanation_map = {

        item["id"]: item["explanation"]

        for item in reasoning.get(
            "reasoned_jobs",
            []
        )
    }

    # ---------------------------------
    # Step 4: Final Ranked Jobs
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

    return {

        "candidate": candidate,

        "ranked_jobs": ranked_jobs,

        "clarifying_question":
            reasoning.get(
                "clarifying_question",
                "Would you prefer AI-focused "
                "roles or backend engineering roles?"
            )
    }


# =============================================================================
# RERANKING ENGINE
# =============================================================================

def refine_recommendations(
    resume_text: str,
    user_feedback: str
) -> dict:

    logger.info(
        "Refining recommendations"
    )

    initial_jobs = rank_jobs(
        resume_text
    )

    prompt = f"""
    Resume:
    {resume_text}

    User Clarification:
    {user_feedback}

    Current Ranked Jobs:
    {json.dumps(initial_jobs, indent=2)}

    Re-rank the jobs based on
    the user clarification.

    Return STRICT JSON ONLY.

    Schema:

    {{
      "ranked_jobs": [
        {{
          "id": 1,
          "similarity_score": 0.95,
          "explanation": "string"
        }}
      ]
    }}
    """

    response = generate_json_response(
        prompt
    )

    if "ranked_jobs" not in response:

        return {
            "ranked_jobs": initial_jobs
        }

    reranked_jobs = []

    for item in response["ranked_jobs"]:

        matched_job = next(

            (
                job for job in jobs_data
                if job["id"] == item["id"]
            ),

            None
        )

        if matched_job:

            reranked_jobs.append({

                "id": matched_job["id"],

                "title": matched_job.get(
                    "title",
                    "Unknown"
                ),

                "company": matched_job.get(
                    "company",
                    "Unknown"
                ),

                "similarity_score":
                    item.get(
                        "similarity_score",
                        0.8
                    ),

                "explanation":
                    item.get(
                        "explanation",
                        "Reranked"
                    )
            })

    return {
        "ranked_jobs": reranked_jobs
    }


# =============================================================================
# ASYNC HELPERS
# =============================================================================

async def async_generate_recommendations(
    resume_text: str
):

    return await asyncio.to_thread(
        generate_recommendations,
        resume_text
    )


async def async_refine_recommendations(
    resume_text: str,
    user_feedback: str
):

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
        "Application startup"
    )

    load_jobs()

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
        "AI-powered job recommendation "
        "and reranking system"
    ),

    version="3.0.0",

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

    StaticFiles(
        directory="static"
    ),

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
# HEALTH CHECK
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

    result = await async_generate_recommendations(
        payload.resume_text
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

    result = await async_refine_recommendations(

        payload.resume_text,

        payload.user_feedback
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
    )
