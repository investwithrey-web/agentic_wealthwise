# Agentic WealthWise

FastAPI-based wealth advisor app with a chat UI, LangGraph agent orchestration, and Finnhub tool-calling for real-time stock quotes.

## Features

- Profile-aware mutual fund and SIP guidance in a browser UI
- LangGraph ReAct agent for tool-driven decisions
- Finnhub quote tool (`get_stock_quote`) for live market data when needed
- FastAPI endpoints for chat and direct quote lookup
- Structured backend logging for route, agent, and tool execution

## Project Structure

- `main.py`: FastAPI backend, LangGraph agent, Finnhub tool, logging
- `wealth_advisor.html`: Frontend UI and client-side prompt/rendering
- `requirements.txt`: Python dependencies

## Requirements

- Python 3.10+
- A valid OpenRouter API key
- A valid Finnhub API key

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Export environment variables:

```bash
export OPENROUTER_API_KEY="your_openrouter_key"
export FINNHUB_API_KEY="your_finnhub_key"
export LOG_LEVEL="INFO"
```

## Run

```bash
uvicorn main:app --reload
```

Open: [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Render Deployment

Use this start command on Render (important: no `--reload`):

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

This is also configured in `render.yaml`.

## API Endpoints

- `GET /`
  - Serves the chat UI (`wealth_advisor.html`)
- `POST /chat`
  - Runs conversation via LangGraph agent
  - Agent can call `get_stock_quote` tool when live quote data is required
- `GET /stock/quote?symbol=AAPL`
  - Returns direct Finnhub quote response (normalized fields)

## How Agentic Tool Calling Works

- The chat request goes to LangGraph ReAct agent.
- The system guardrail instructs the model to call `get_stock_quote` for live/current/intraday quote questions.
- The tool fetches Finnhub quote data and returns it to the model.
- If Finnhub fails for a symbol, the tool returns structured error output so chat can still continue gracefully.

## Logging

The backend logs:

- route starts/success/errors
- LangGraph runtime and response size
- Finnhub tool call lifecycle (start/success/failure/no-data)

Set verbosity:

```bash
export LOG_LEVEL="DEBUG"
```

## Notes

- Use valid ticker formats like `AAPL`, `MSFT`, `INFY.NS`.
- Some tickers/markets may be restricted by Finnhub plan and return `403`.