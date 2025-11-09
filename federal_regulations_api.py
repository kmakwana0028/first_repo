from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
from typing import Dict
import asyncio
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Federal Register Documents Tracker")

# Use Federal Register API - fully functional and documented
FR_API_BASE = "https://www.federalregister.gov/api/v1"
MAX_CONCURRENT = 10  # Increased for faster parallel processing
TIMEOUT = 120
DOCUMENTS_PER_AGENCY = 20  # Reduced to speed up initial load (was 50)

_cache = None
_cache_timestamp = None

# CFR Title to Agency mapping (50 titles from www.ecfr.gov)
CFR_TITLE_TO_AGENCY = {
    1: "General Provisions",
    2: "Grants and Agreements",
    3: "The President",
    4: "Accounts",
    5: "Administrative Personnel",
    6: "Domestic Security",
    7: "Agriculture",
    8: "Aliens and Nationality",
    9: "Animals and Animal Products",
    10: "Energy",
    11: "Federal Elections",
    12: "Banks and Banking",
    13: "Business Credit and Assistance",
    14: "Aeronautics and Space",
    15: "Commerce and Foreign Trade",
    16: "Commercial Practices",
    17: "Commodity and Securities Exchanges",
    18: "Conservation of Power and Water Resources",
    19: "Customs Duties",
    20: "Employees' Benefits",
    21: "Food and Drugs",
    22: "Foreign Relations",
    23: "Highways",
    24: "Housing and Urban Development",
    25: "Indians",
    26: "Internal Revenue",
    27: "Alcohol, Tobacco Products and Firearms",
    28: "Judicial Administration",
    29: "Labor",
    30: "Mineral Resources",
    31: "Money and Finance: Treasury",
    32: "National Defense",
    33: "Navigation and Navigable Waters",
    34: "Education",
    35: "Panama Canal",
    36: "Parks, Forests, and Public Property",
    37: "Patents, Trademarks, and Copyrights",
    38: "Pensions, Bonuses, and Veterans' Relief",
    39: "Postal Service",
    40: "Protection of Environment",
    41: "Public Contracts and Property Management",
    42: "Public Health",
    43: "Public Lands: Interior",
    44: "Emergency Management and Assistance",
    45: "Public Welfare",
    46: "Shipping",
    47: "Telecommunication",
    48: "Federal Acquisition Regulations System",
    49: "Transportation",
    50: "Wildlife and Fisheries",
}

# Agency name keywords to match Federal Register agencies with CFR titles
AGENCY_KEYWORDS_MAP = {
    "Agriculture": 7,
    "Air Force": 32,
    "Army": 32,
    "Coast Guard": 33,
    "Commerce": 15,
    "Defense": 32,
    "Education": 34,
    "Energy": 10,
    "Environmental Protection": 40,
    "Federal Aviation": 14,
    "Federal Communications": 47,
    "Federal Election": 11,
    "Federal Trade": 16,
    "Food and Drug": 21,
    "Health and Human Services": 42,
    "Homeland Security": 6,
    "Housing and Urban Development": 24,
    "Interior": 43,
    "Internal Revenue": 26,
    "Justice": 28,
    "Labor": 29,
    "National Aeronautics": 14,
    "Navy": 32,
    "Nuclear Regulatory": 10,
    "Postal Service": 39,
    "Securities and Exchange": 17,
    "Small Business": 13,
    "Social Security": 20,
    "State Department": 22,
    "Transportation": 49,
    "Treasury": 31,
    "Veterans Affairs": 38,
}

# -----------------------------
# Helper Functions
# -----------------------------
def is_within_24_hours(publication_date: str) -> bool:
    """Check if a document was published within the last 24 hours."""
    try:
        pub_date = datetime.fromisoformat(publication_date.replace('Z', '+00:00'))
        now = datetime.now(pub_date.tzinfo)
        return (now - pub_date) < timedelta(hours=24)
    except:
        return False

def estimate_document_size(doc_type: str) -> int:
    """Estimate document size in KB based on type."""
    size_map = {
        "Rule": 150,
        "Proposed Rule": 120,
        "Notice": 80,
        "Presidential Document": 100,
    }
    return size_map.get(doc_type, 50)

def matches_cfr_agency(agency_name: str) -> bool:
    """Check if an agency name matches one of the 50 CFR title agencies."""
    agency_upper = agency_name.upper()

    # Check against known keywords that map to CFR titles
    for keyword in AGENCY_KEYWORDS_MAP.keys():
        if keyword.upper() in agency_upper:
            return True

    # Also check against CFR title names
    for title_name in CFR_TITLE_TO_AGENCY.values():
        if title_name.upper() in agency_upper or agency_upper in title_name.upper():
            return True

    return False

# -----------------------------
# Fetch all agencies from Federal Register
# -----------------------------
async def fetch_all_agencies():
    """Fetch list of all federal agencies from Federal Register API."""
    url = f"{FR_API_BASE}/agencies"
    logger.info(f"Fetching agencies from: {url}")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            agencies = r.json()
            logger.info(f"Successfully fetched {len(agencies)} agencies")
            return agencies
        except Exception as e:
            logger.error(f"Failed to fetch agencies: {e}")
            raise

# -----------------------------
# Fetch recent documents for a single agency
# -----------------------------
async def fetch_agency_documents(agency_slug: str, agency_name: str, limit: int = DOCUMENTS_PER_AGENCY):
    """Fetch recent Federal Register documents for a specific agency."""
    url = f"{FR_API_BASE}/documents"

    # Get documents from the last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    params = {
        "conditions[agencies][]": agency_slug,
        "conditions[publication_date][gte]": thirty_days_ago,
        "per_page": limit,
        "order": "newest",
        "fields[]": ["title", "document_number", "publication_date", "type",
                     "pdf_url", "html_url", "abstract"]
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

            documents = []
            total_count = data.get("count", 0)

            for doc in data.get("results", []):
                doc_type = doc.get("type", "Unknown")
                pub_date = doc.get("publication_date", "")
                size_kb = estimate_document_size(doc_type)

                documents.append({
                    "title": doc.get("title", "Untitled"),
                    "document_number": doc.get("document_number", ""),
                    "publication_date": pub_date,
                    "type": doc_type,
                    "size_kb": size_kb,
                    "pdf_url": doc.get("pdf_url", ""),
                    "html_url": doc.get("html_url", ""),
                    "abstract": doc.get("abstract", "")[:200] + "..." if doc.get("abstract") else "",
                    "is_new": is_within_24_hours(pub_date)
                })

            logger.info(f"Agency '{agency_name}': fetched {len(documents)} recent documents (total: {total_count})")
            return documents, total_count

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch documents for {agency_name}: {e.response.status_code}")
            return [], 0
        except Exception as e:
            logger.error(f"Error fetching documents for {agency_name}: {e}")
            return [], 0

# -----------------------------
# Aggregate agency statistics with documents
# -----------------------------
async def aggregate_agency_statistics():
    """Aggregate Federal Register document counts and recent documents by agency."""
    agencies = await fetch_all_agencies()

    # Filter to only include agencies that correspond to the 50 CFR titles
    cfr_agencies = [a for a in agencies if matches_cfr_agency(a.get("name", ""))]

    logger.info(f"Processing {len(cfr_agencies)} CFR-related agencies (filtered from {len(agencies)} total Federal Register agencies)")

    agency_stats: Dict[str, dict] = {}
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def process_agency(agency):
        async with sem:
            try:
                agency_slug = agency.get("slug")
                agency_name = agency.get("name", "Unknown")
                short_name = agency.get("short_name", "")

                # Fetch recent documents for this agency
                documents, total_count = await fetch_agency_documents(agency_slug, agency_name)

                # Use short name if available, otherwise full name
                display_name = short_name if short_name else agency_name

                # Calculate total size from documents
                total_size_kb = sum(doc["size_kb"] for doc in documents)

                # Count new documents (within 24 hours)
                new_docs_count = sum(1 for doc in documents if doc["is_new"])

                agency_stats[display_name] = {
                    "document_count": total_count,
                    "recent_documents": documents,
                    "new_documents_count": new_docs_count,
                    "size_mb": round(total_size_kb / 1024, 4),
                    "agency_id": agency.get("id"),
                    "slug": agency_slug,
                    "url": agency.get("agency_url", ""),
                    "full_name": agency_name
                }

            except Exception as e:
                logger.error(f"Failed to process agency {agency.get('name', 'unknown')}: {e}")

    await asyncio.gather(*(process_agency(a) for a in cfr_agencies))

    # Remove agencies with zero documents
    agency_stats = {k: v for k, v in agency_stats.items() if v["document_count"] > 0}

    logger.info(f"Processed {len(agency_stats)} CFR agencies with documents")

    return agency_stats

# -----------------------------
# Fetch all recent documents (last 24 hours)
# -----------------------------
async def fetch_recent_documents_all():
    """Fetch all documents published in the last 24 hours across all agencies."""
    url = f"{FR_API_BASE}/documents"

    yesterday = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d")

    params = {
        "conditions[publication_date][gte]": yesterday,
        "per_page": 100,
        "order": "newest",
        "fields[]": ["title", "document_number", "publication_date", "type",
                     "pdf_url", "html_url", "agencies"]
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

            recent_docs = []
            for doc in data.get("results", []):
                # Get first agency name
                agencies = doc.get("agencies", [])
                agency_name = agencies[0].get("name", "Unknown") if agencies else "Unknown"

                doc_type = doc.get("type", "Unknown")
                size_kb = estimate_document_size(doc_type)

                recent_docs.append({
                    "title": doc.get("title", "Untitled"),
                    "document_number": doc.get("document_number", ""),
                    "publication_date": doc.get("publication_date", ""),
                    "type": doc_type,
                    "agency": agency_name,
                    "size_kb": size_kb,
                    "pdf_url": doc.get("pdf_url", ""),
                    "html_url": doc.get("html_url", "")
                })

            logger.info(f"Fetched {len(recent_docs)} documents from last 24 hours")
            return recent_docs

        except Exception as e:
            logger.error(f"Error fetching recent documents: {e}")
            return []

# -----------------------------
# Routes
# -----------------------------
@app.get("/api/agency-stats")
async def agency_statistics():
    """Get agency statistics with recent documents in JSON format."""
    global _cache, _cache_timestamp

    if _cache is None:
        logger.info("Cache empty, fetching data...")
        _cache = await aggregate_agency_statistics()
        _cache_timestamp = datetime.now().isoformat()

    return {
        "last_updated": _cache_timestamp,
        "total_agencies": len(_cache),
        "agencies": _cache
    }

@app.get("/api/recent")
async def recent_documents():
    """Get all documents from the last 24 hours."""
    docs = await fetch_recent_documents_all()
    return {
        "count": len(docs),
        "documents": docs
    }

@app.get("/api/agency/{slug}")
async def agency_details(slug: str):
    """Get detailed documents for a specific agency."""
    global _cache

    if _cache is None:
        _cache = await aggregate_agency_statistics()

    # Find agency by slug
    for agency_name, data in _cache.items():
        if data["slug"] == slug:
            return data

    return JSONResponse(
        status_code=404,
        content={"error": f"Agency with slug '{slug}' not found"}
    )

@app.get("/refresh")
async def refresh_cache():
    """Force refresh the cache."""
    global _cache, _cache_timestamp

    logger.info("Manual cache refresh requested")
    _cache = await aggregate_agency_statistics()
    _cache_timestamp = datetime.now().isoformat()

    return {
        "status": "success",
        "last_updated": _cache_timestamp,
        "total_agencies": len(_cache)
    }

@app.get("/recent", response_class=HTMLResponse)
async def recent_documents_page():
    """Display recent documents (last 24 hours) in HTML."""
    docs = await fetch_recent_documents_all()

    rows = ""
    for doc in docs:
        pdf_link = f'<a href="{doc["pdf_url"]}" target="_blank">PDF</a>' if doc["pdf_url"] else ""
        html_link = f'<a href="{doc["html_url"]}" target="_blank">HTML</a>' if doc["html_url"] else ""

        rows += f"""
        <tr>
            <td><span class="new-badge">NEW</span> {doc['title'][:100]}...</td>
            <td>{doc['agency']}</td>
            <td>{doc['type']}</td>
            <td>{doc['publication_date']}</td>
            <td style="text-align: right;">{doc['size_kb']} KB</td>
            <td>{pdf_link} {html_link}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Recent Federal Register Documents (24 Hours)</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
            h1 {{ color: #333; border-bottom: 3px solid: #d9534f; }}
            .new-badge {{ background-color: #d9534f; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th {{ background-color: #d9534f; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            tr:hover {{ background-color: #f5f5f5; }}
            a {{ color: #0066cc; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📢 Recent Federal Register Documents (Last 24 Hours)</h1>
            <p>Found {len(docs)} new documents.</p>
            <p><a href="/">← Back to All Agencies</a></p>

            <table>
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Agency</th>
                        <th>Type</th>
                        <th>Published</th>
                        <th>Size</th>
                        <th>Links</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return html

@app.get("/", response_class=HTMLResponse)
async def index():
    """Display agency statistics with expandable document details."""
    global _cache, _cache_timestamp

    if _cache is None:
        logger.info("Cache empty, fetching data...")
        _cache = await aggregate_agency_statistics()
        _cache_timestamp = datetime.now().isoformat()

    # Sort agencies alphabetically by name
    sorted_agencies = sorted(
        _cache.items(),
        key=lambda x: x[0].lower()  # Sort by agency name (case-insensitive)
    )

    # Calculate totals
    total_docs = sum(data["document_count"] for _, data in sorted_agencies)
    total_new = sum(data["new_documents_count"] for _, data in sorted_agencies)
    total_size = sum(data["size_mb"] for _, data in sorted_agencies)

    # Generate table rows with expandable document lists (optimized with list comprehension)
    def generate_row(agency, data):
        agency_url = data.get("url", "")
        full_name = data.get("full_name", agency)
        doc_count = data["document_count"]
        new_count = data["new_documents_count"]
        size_mb = data["size_mb"]
        documents = data.get("recent_documents", [])

        # Agency name with link
        agency_display = f'<a href="{agency_url}" target="_blank">{agency}</a>' if agency_url else agency
        new_badge = f'<span class="new-badge">{new_count} NEW</span>' if new_count > 0 else ''

        # Generate document list using list comprehension for better performance
        doc_items = []
        for doc in documents[:10]:  # Show first 10 documents
            new_indicator = '🔴 ' if doc["is_new"] else ''
            pdf_link = f'<a href="{doc["pdf_url"]}" target="_blank" class="doc-link">PDF</a>' if doc["pdf_url"] else ''
            html_link = f'<a href="{doc["html_url"]}" target="_blank" class="doc-link">HTML</a>' if doc["html_url"] else ''

            doc_items.append(f'''
            <div class="document-item">
                <div class="doc-title">{new_indicator}{doc['title']}</div>
                <div class="doc-meta">
                    <span>{doc['type']}</span> |
                    <span>{doc['publication_date']}</span> |
                    <span>{doc['size_kb']} KB</span> |
                    {pdf_link} {html_link}
                </div>
            </div>''')

        doc_list = ''.join(doc_items) if doc_items else '<p>No recent documents</p>'
        show_more = f'<p class="show-more">Showing 10 of {len(documents)} recent documents</p>' if len(documents) > 10 else ''

        return f'''
        <tr class="agency-row" onclick="toggleDocuments('docs-{data['agency_id']}')">
            <td>{agency_display} {new_badge}</td>
            <td style="font-size: 0.85em; color: #666;">{full_name if full_name != agency else ''}</td>
            <td style="text-align: right;">{doc_count:,}</td>
            <td style="text-align: right;">{size_mb:.2f}</td>
            <td style="text-align: center;">▼</td>
        </tr>
        <tr id="docs-{data['agency_id']}" class="documents-row" style="display: none;">
            <td colspan="5">
                <div class="documents-container">
                    <h4>Recent Documents (Last 30 Days)</h4>
                    {doc_list}
                    {show_more}
                </div>
            </td>
        </tr>'''

    # Build all rows efficiently using join
    rows = ''.join(generate_row(agency, data) for agency, data in sorted_agencies)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Federal Regulations-eCFRs Analysis</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1600px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                border-bottom: 3px solid #0066cc;
                padding-bottom: 10px;
            }}
            .metadata {{
                background-color: #f0f8ff;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border-left: 4px solid #0066cc;
            }}
            .metadata strong {{
                display: inline-block;
                min-width: 150px;
            }}
            .new-badge {{
                background-color: #d9534f;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.75em;
                font-weight: bold;
                margin-left: 8px;
            }}
            .ecfr-btn {{
                background-color: #5cb85c;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.75em;
                text-decoration: none;
                margin-left: 8px;
                display: inline-block;
            }}
            .ecfr-btn:hover {{
                background-color: #449d44;
                text-decoration: none;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th {{
                background-color: #0066cc;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 10px;
                border-bottom: 1px solid #ddd;
            }}
            .agency-row {{
                cursor: pointer;
            }}
            .agency-row:hover {{
                background-color: #f5f5f5;
            }}
            .documents-row {{
                background-color: #f9f9f9;
            }}
            .documents-container {{
                padding: 20px;
                max-height: 500px;
                overflow-y: auto;
            }}
            .document-item {{
                padding: 10px;
                margin-bottom: 10px;
                border-left: 3px solid #0066cc;
                background-color: white;
            }}
            .doc-title {{
                font-weight: bold;
                margin-bottom: 5px;
                color: #333;
            }}
            .doc-meta {{
                font-size: 0.85em;
                color: #666;
            }}
            .doc-link {{
                color: #0066cc;
                text-decoration: none;
                padding: 2px 6px;
                border: 1px solid #0066cc;
                border-radius: 3px;
                font-size: 0.85em;
            }}
            .doc-link:hover {{
                background-color: #0066cc;
                color: white;
            }}
            .show-more {{
                color: #666;
                font-style: italic;
                margin-top: 10px;
            }}
            .button {{
                background-color: #0066cc;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                display: inline-block;
                margin: 10px 5px 10px 0;
            }}
            .button:hover {{
                background-color: #0052a3;
            }}
            .button.alert {{
                background-color: #d9534f;
            }}
            .button.alert:hover {{
                background-color: #c9302c;
            }}
            .footer {{
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                color: #666;
                font-size: 0.9em;
            }}
            a {{
                color: #0066cc;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
        </style>
        <script>
            function toggleDocuments(id) {{
                var row = document.getElementById(id);
                if (row.style.display === 'none') {{
                    row.style.display = 'table-row';
                }} else {{
                    row.style.display = 'none';
                }}
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <h1>📋 Federal Regulations-eCFRs Analysis</h1>

            <div class="metadata">
                <strong>Last Updated:</strong> {_cache_timestamp or 'Never'}<br>
                <strong>Total Agencies:</strong> {len(_cache)}<br>
                <strong>Total Documents:</strong> {total_docs:,}<br>
                <strong>New in 24hrs:</strong> <span class="new-badge">{total_new}</span><br>
                <strong>Estimated Total Size:</strong> {total_size:.2f} MB<br>
                <a href="/refresh" class="button">🔄 Refresh Data</a>
                <a href="/recent" class="button alert">🔴 View All New (24hrs)</a>
                <a href="/api/agency-stats" class="button">📊 JSON API</a>
            </div>

            <p><strong>💡 Tip:</strong> Click on any agency row to expand and see recent Federal Register documents. Documents with 🔴 were published in the last 24 hours.</p>

            <table>
                <thead>
                    <tr>
                        <th>Agency</th>
                        <th>Full Name</th>
                        <th style="text-align: right;">Total Docs</th>
                        <th style="text-align: right;">Size (MB)</th>
                        <th style="text-align: center;">Expand</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>

            <div class="footer">
                <p><strong>Note:</strong> This page tracks NEW regulatory documents published in the Federal Register. Click any row to see recent documents (last 30 days).
                Documents marked with 🔴 were published within the last 24 hours.</p>
                <p><strong>Data Source:</strong> <a href="https://www.federalregister.gov" target="_blank">Federal Register API</a> (daily publications, notices, proposed & final rules)<br>
                <strong>Reference:</strong> <a href="https://www.ecfr.gov" target="_blank">Electronic Code of Federal Regulations (eCFR)</a> (codified regulations)</p>
                <p style="font-size: 0.9em; color: #666; font-style: italic;">
                The Federal Register publishes new regulatory documents daily. These documents are later codified into the eCFR, which contains the official text of current regulations organized by Title and Part.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html
