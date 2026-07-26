import os
from contextlib import asynccontextmanager

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

from rag_loop import get_answer, load_entity_names

load_dotenv()

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]
    openai_api_key = os.environ["OPENAI_API_KEY"]
    state["client"] = OpenAI(api_key=openai_api_key)
    state["conn"] = psycopg.connect(database_url, autocommit=True)
    with state["conn"].cursor() as cur:
        state["entity_names"] = load_entity_names(cur)
    yield
    state["conn"].close()


app = FastAPI(lifespan=lifespan)

# Allow the Electron renderer (loaded via file://) to call this server. This is a
# personal-use, localhost-only tool - not exposed beyond the local machine - so an
# open CORS policy is fine here and avoids chasing the exact file:// origin string.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    with state["conn"].cursor() as cur:
        result = get_answer(state["client"], cur, req.question, state["entity_names"])
    return {"answer": result["answer"]}
