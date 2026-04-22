
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
import json
import logging
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
from requests import RequestException

try:
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False

app = FastAPI()

API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "d7jtv1pr01qnk4ocshqgd7jtv1pr01qnk4ocshr0")
BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "wealth_advisor.html"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("wealthwise")


class ChatRequest(BaseModel):
    messages: list


def fetch_finnhub_quote(symbol: str) -> dict:
    logger.info("finnhub.quote.start symbol=%s", symbol)
    if not FINNHUB_API_KEY:
        logger.error("finnhub.quote.missing_api_key")
        raise HTTPException(status_code=500, detail="FINNHUB_API_KEY is not set")

    try:
        started = time.perf_counter()
        res = requests.get(
            FINNHUB_QUOTE_URL,
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=12
        )
        res.raise_for_status()
        quote = res.json()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("finnhub.quote.success symbol=%s status=%s elapsed_ms=%s", symbol, res.status_code, elapsed_ms)
    except RequestException as exc:
        logger.exception("finnhub.quote.failed symbol=%s", symbol)
        raise HTTPException(status_code=502, detail=f"Finnhub request failed: {exc}") from exc

    # Finnhub returns c=0 or missing fields for invalid/unavailable symbols.
    if not quote or quote.get("c") in (None, 0):
        logger.warning("finnhub.quote.no_data symbol=%s payload=%s", symbol, quote)
        raise HTTPException(status_code=404, detail=f"No live quote data for symbol: {symbol}")

    return {
        "symbol": symbol,
        "current": quote.get("c"),
        "change": quote.get("d"),
        "percent_change": quote.get("dp"),
        "high": quote.get("h"),
        "low": quote.get("l"),
        "open": quote.get("o"),
        "previous_close": quote.get("pc"),
        "timestamp": quote.get("t"),
    }


if LANGGRAPH_AVAILABLE:
    @tool
    def get_stock_quote(symbol: str) -> str:
        """Fetch real-time stock quote from Finnhub for a ticker symbol (e.g., AAPL, TSLA, INFY.NS)."""
        logger.info("tool.get_stock_quote.called symbol=%s", symbol)
        normalized = symbol.strip().upper()
        try:
            payload = fetch_finnhub_quote(normalized)
            logger.info("tool.get_stock_quote.return symbol=%s current=%s", payload.get("symbol"), payload.get("current"))
            return json.dumps(payload)
        except HTTPException as exc:
            # Tool errors should be returned as tool output so the agent can recover
            # and suggest alternatives, instead of crashing the whole /chat call.
            logger.warning(
                "tool.get_stock_quote.error symbol=%s status=%s detail=%s",
                normalized,
                exc.status_code,
                exc.detail,
            )
            return json.dumps(
                {
                    "symbol": normalized,
                    "error": str(exc.detail),
                    "status_code": exc.status_code,
                    "hint": "Try a supported ticker format (e.g. AAPL, MSFT, INFY.NS).",
                }
            )


def convert_messages_for_langgraph(messages: list):
    converted = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if role == "system":
            converted.append(SystemMessage(content=content))
        elif role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
    return converted


def run_langgraph_agent(messages: list):
    if not LANGGRAPH_AVAILABLE:
        logger.error("langgraph.unavailable_missing_packages")
        raise HTTPException(
            status_code=500,
            detail=(
                "LangGraph dependencies not installed. Install with: "
                "pip install langgraph langchain langchain-openai"
            ),
        )

    logger.info("langgraph.agent.start messages_count=%s", len(messages))
    llm = ChatOpenAI(
        api_key=API_KEY,
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-oss-120b:free",
        temperature=0,
    )

    system_guardrail = (
        "You are WealthWise. Use the get_stock_quote tool whenever the user asks for live/current/"
        "real-time stock price, intraday movement, or market quote for any ticker."
    )

    graph = create_react_agent(
        model=llm,
        tools=[get_stock_quote],
        prompt=system_guardrail,
    )

    started = time.perf_counter()
    response = graph.invoke({"messages": convert_messages_for_langgraph(messages)})
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    final_message = response["messages"][-1]
    logger.info("langgraph.agent.success elapsed_ms=%s response_chars=%s", elapsed_ms, len(str(final_message.content)))
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": final_message.content,
                }
            }
        ]
    }


@app.get("/")
def home():
    logger.info("route.home")
    if not HTML_PATH.exists():
        logger.error("route.home.html_missing path=%s", HTML_PATH)
        raise HTTPException(status_code=404, detail="wealth_advisor.html not found")
    return FileResponse(HTML_PATH)


@app.get("/stock/quote")
def stock_quote(symbol: str):
    logger.info("route.stock_quote symbol=%s", symbol)
    return fetch_finnhub_quote(symbol.strip().upper())


@app.post("/chat")
def chat(req: ChatRequest):
    logger.info("route.chat.start messages_count=%s", len(req.messages))
    try:
        result = run_langgraph_agent(req.messages)
        logger.info("route.chat.success")
        return result
    except HTTPException:
        logger.exception("route.chat.http_exception")
        raise
    except Exception as exc:
        logger.exception("route.chat.unhandled_exception")
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)