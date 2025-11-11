# Federal Regulations-eCFRs Analysis

A python based application that tracks and displays federal regulatory documents from the Federal Register, organized by agency with estimated document sizes.

## Features

- **Real-time Federal Register Tracking**: Fetches the latest documents from federal agencies via the Federal Register API
- **Agency Statistics**: Aggregates documents by agency with estimated sizes
- **Recent Documents Monitoring**: Highlights documents published within the last 24 hours
- **Interactive Web Interface**: Expandable tables showing detailed document information
- **REST API**: JSON endpoints for programmatic access to statistics
- **50 CFR Agency Filter**: Displays only agencies corresponding to the 50 CFR titles
- **Alphabetical Sorting**: Agencies sorted alphabetically for easy navigation
- **Document Size Estimation**: Estimates document sizes based on document type

## API Endpoints

- **`/`** - Main HTML dashboard with agency statistics
- **`/api/agency-stats`** - JSON endpoint for agency statistics
- **`/api/recent`** - JSON endpoint for documents from last 24 hours
- **`/api/agency/{slug}`** - JSON endpoint for specific agency details
- **`/recent`** - HTML page showing all documents from last 24 hours
- **`/refresh`** - Force refresh the cache and fetch latest data

## Project Structure

```
xyz/
├── app/
│   ├── federal_regulations_api.py      # Main FastAPI application (size estimation)
│   └── federal_regulations_wc_api.py   # Word count version
├── requirements.txt                     # Python dependencies
└── README_federal_regulations_api.md                            # Main README
```

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- Internet connection (for accessing Federal Register API)

## Installation

### 1. Unzip the file

```bash
cd /path/to/app
```

### 2. Create a Virtual Environment (Recommended)

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install packages individually:
```bash
pip install fastapi uvicorn httpx
```

## Running the Application

### Start the Server

**Using uvicorn directly:**
```bash
uvicorn app.federal_regulations_api:app --reload
```

**Or with host and port specification:**
```bash
uvicorn app.federal_regulations_api:app --host 0.0.0.0 --port 8000 --reload
```

**Using Python module:**
```bash
python -m uvicorn app.federal_regulations_api:app --reload
```

### Command Options

- `--reload`: Enable auto-reload on code changes (development mode)
- `--host 0.0.0.0`: Make server accessible from other devices on the network
- `--port 8000`: Specify the port (default: 8000)


## Accessing the Application

Once the server is running, access the application through your web browser:

- **Main Dashboard**: http://localhost:8000/
- **Recent Documents (24hrs)**: http://localhost:8000/recent
- **JSON API - Agency Stats**: http://localhost:8000/api/agency-stats
- **JSON API - Recent Docs**: http://localhost:8000/api/recent
- **Refresh Cache**: http://localhost:8000/refresh
- **API Documentation**: http://localhost:8000/docs


## How It Works

1. The application fetches agencies from the Federal Register API
2. Filters agencies to match only the 50 CFR title agencies using keyword mapping
3. For each matching agency, retrieves recent documents from the last 30 days
4. Estimates document sizes based on document type
5. Highlights documents published in the last 24 hours
6. Removes agencies with zero documents
7. Sorts agencies alphabetically and displays in an interactive HTML interface

## CFR Titles Covered

The application tracks agencies corresponding to all 50 CFR titles:

1. General Provisions
2. Grants and Agreements
3. The President
4. Accounts
5. Administrative Personnel
6. Domestic Security
7. Agriculture
8. Aliens and Nationality
9. Animals and Animal Products
10. Energy
... and 40 more (see [federal_regulations_api.py](app/federal_regulations_api.py) for complete list)

## Troubleshooting

### Connection Issues

If you encounter connection errors:
- Verify your internet connection
- Check if the Federal Register API is accessible: https://www.federalregister.gov/api/v1/agencies

### Port Already in Use

If port 8000 is already in use:
```bash
uvicorn app.federal_regulations_api:app --port 8001 --reload
```

## System Requirements

### Minimum Requirements
- **RAM**: 512 MB
- **CPU**: 1 core
- **Disk Space**: 100 MB
- **Network**: Stable internet connection

### Recommended Requirements
- **RAM**: 2 GB or more
- **CPU**: 2+ cores
- **Disk Space**: 500 MB
- **Network**: High-speed internet connection

# Install Python (if not installed)

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.federal_regulations_api:app --reload
```

## Technologies Used

- **FastAPI**: Modern Python web framework for building APIs
- **httpx**: Async HTTP client for API requests
- **uvicorn**: ASGI server for running FastAPI
- **Python asyncio**: Asynchronous programming for concurrent requests
- **Federal Register API**: Government API for regulatory documents

## Data Source

This application uses the official [Federal Register API](https://www.federalregister.gov/developers/api/v1) to fetch real-time regulatory documents from federal agencies.

**Reference:** [Electronic Code of Federal Regulations (eCFR)](https://www.ecfr.gov)


## License

This project is provided as-is for educational and informational purposes.

## Updates

The application automatically fetches the latest data from the Federal Register API. Use the "Refresh Data" button in the web interface to manually update the cache.
