# Flight Search GUI

Python desktop application for searching flights, tracking saved routes, and plotting price history.

Phase 1 uses Tkinter for the first GUI version.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-app.txt
python main.py
```

## Configuration

Create a local `.env` from `.env.example` and keep it out of Git.

Use mock data without API credentials:

```text
FLIGHT_API_PROVIDER=mock
```

Use Amadeus Self-Service once you have an API key and secret:

```text
FLIGHT_API_PROVIDER=amadeus
AMADEUS_CLIENT_ID=your_client_id
AMADEUS_CLIENT_SECRET=your_client_secret
```

The app reads default currency, default origin, database path, provider choice, and Amadeus credentials from environment variables or `.env`.
