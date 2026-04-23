
# import requests
# import json

# # Hardcoded API key (not recommended for production)
# API_KEY = "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"

# url = "https://openrouter.ai/api/v1/chat/completions"

# headers = {
#     "Authorization": f"Bearer {API_KEY}",
#     "Content-Type": "application/json"
# }

# data = {
#     "model": "openai/gpt-oss-120b:free",
#     "messages": [
#         {
#             "role": "user",
#             "content": "Explain mutual funds in simple terms"
#         }
#     ]
# }

# response = requests.post(url, headers=headers, data=json.dumps(data))

# # Print response
# print(response.status_code)
# print(response.json())


# from fastapi import FastAPI
# from pydantic import BaseModel
# import requests
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI()

# # Enable CORS (important)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # restrict in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# API_KEY = "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"
# OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# # Request schema
# class ChatRequest(BaseModel):
#     messages: list

# @app.post("/chat")
# async def chat(req: ChatRequest):
#     response = requests.post(
#         OPENROUTER_URL,
#         headers={
#             "Authorization": f"Bearer {API_KEY}",
#             "Content-Type": "application/json"
#         },
#         json={
#             "model": "openai/gpt-oss-120b:free",
#             "messages": req.messages
#         }
#     )

#     return response.json()

import os
import logging
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("wealthwise")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openai/gpt-oss-120b:free"
BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "wealth_advisor.html"


class ChatRequest(BaseModel):
    messages: list


@app.get("/")
def home():
    logger.info("route.home")
    if not HTML_PATH.exists():
        logger.error("route.home.html_missing path=%s", HTML_PATH)
        raise HTTPException(status_code=404, detail="wealth_advisor.html not found")
    return FileResponse(HTML_PATH)


@app.post("/chat")
def chat(req: ChatRequest):
    logger.info("route.chat.start messages_count=%s", len(req.messages))
    if not OPENROUTER_API_KEY:
        logger.error("route.chat.missing_openrouter_api_key")
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": req.messages,
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=40)
        response.raise_for_status()
        logger.info("route.chat.success status=%s", response.status_code)
        return response.json()
    except requests.RequestException as exc:
        logger.exception("route.chat.request_failed")
        raise HTTPException(status_code=502, detail=f"LLM API request failed: {exc}") from exc


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8051))
    uvicorn.run(app, host="0.0.0.0", port=port)