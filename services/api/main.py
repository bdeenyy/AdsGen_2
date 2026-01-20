"""
AdsGen 2.0 - API Gateway
Main FastAPI application for the AdsGen platform
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.config import get_settings
from services.shared.database import init_db, get_session
from services.shared.models.vacancy import Vacancy, VacancyStatus
from services.shared.schemas.vacancy import (
    HealthResponse,
    TaskResponse,
    VacancyResponse,
    VacancyListResponse,
)
from services.shared.utils import GoogleSheetsService

settings = get_settings()
templates = Jinja2Templates(directory="services/api/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle handler."""
    await init_db()
    yield


app = FastAPI(
    title="AdsGen 2.0 API",
    description="Worker-based job advertisement generation platform",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health status."""
    return HealthResponse(
        status="healthy",
        database="connected",
        redis="connected",
        comfyui="configured" if settings.comfyui_url else None,
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - Control Panel."""
    return templates.TemplateResponse("index.html", {"request": request})


# ═══════════════════════════════════════════════════════════════════════════
# IMPORT ENDPOINT (JSON-only)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/import/json", response_model=TaskResponse)
async def import_json(
    data: list[dict] = Body(...),
    cities: Optional[list[str]] = Query(None)
):
    """Import vacancies directly as JSON data."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.import_worker.tasks.process_json_import",
        args=[data, cities]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"JSON import started for {len(data)} rows",
    )



@app.post("/google/sheets/meta")
async def get_sheet_meta(url: str = Body(..., embed=True)):
    """Get list of sheets from a Google Spreadsheet."""
    if not settings.google_credentials_json:
        raise HTTPException(status_code=500, detail="Google credentials not configured")
        
    try:
        gs_service = GoogleSheetsService(settings.google_credentials_json)
        sheets = gs_service.get_sheet_names(url)
        return {"sheets": sheets}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/google/sheets/headers")
async def get_sheet_headers(
    url: str = Body(..., embed=True),
    sheet_name: str = Body(..., embed=True)
):
    """Get headers from a specific sheet."""
    if not settings.google_credentials_json:
        raise HTTPException(status_code=500, detail="Google credentials not configured")
        
    try:
        gs_service = GoogleSheetsService(settings.google_credentials_json)
        headers = gs_service.get_sheet_headers(url, sheet_name)
        return {"headers": headers}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/import/sheets", response_model=TaskResponse)
async def import_sheets(
    spreadsheet_input: str = Body(..., description="Spreadsheet ID or URL"),
    sheet_name: Optional[str] = Body(None),
    cities: Optional[list[str]] = Body(None),
    column_mapping: Optional[dict] = Body(None)
):
    """
    Import vacancies from Google Sheets.
    """
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.import_worker.tasks.import_spreadsheet",
        args=[spreadsheet_input, sheet_name, cities, column_mapping]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Google Sheets import started for {spreadsheet_input}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# GENERATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/generate/text/{vacancy_id}", response_model=TaskResponse)
async def generate_text(vacancy_id: str):
    """Generate text content (title + description) for a vacancy."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.textgen_worker.tasks.generate_vacancy_text",
        args=[vacancy_id]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Text generation started for vacancy: {vacancy_id}",
    )


@app.post("/generate/image/{vacancy_id}", response_model=TaskResponse)
async def generate_image(vacancy_id: str, gender: str = None, age: int = None):
    """Generate image for a vacancy."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.imagegen_worker.tasks.generate_vacancy_image",
        args=[vacancy_id, gender, age]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Image generation started for vacancy: {vacancy_id}",
    )


@app.post("/generate/batch", response_model=TaskResponse)
async def generate_batch(status_filter: str = "pending", limit: int = 50):
    """Start batch generation for all pending vacancies."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.import_worker.tasks.start_batch_processing",
        args=[status_filter, limit]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Batch processing started for {limit} vacancies",
    )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION & PUBLISHING
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/validate/{vacancy_id}", response_model=TaskResponse)
async def validate_vacancy(vacancy_id: str):
    """Validate vacancy content against Avito rules."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.validation_worker.tasks.validate_vacancy_content",
        args=[vacancy_id]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message=f"Validation started for vacancy: {vacancy_id}",
    )


@app.post("/publish/xml", response_model=TaskResponse)
async def export_xml(vacancy_ids: list[str] = None):
    """Export vacancies to Avito XML format."""
    from services.shared.celery_app import celery_app
    task = celery_app.send_task(
        "services.publisher_worker.tasks.export_to_xml",
        args=[vacancy_ids]
    )
    
    return TaskResponse(
        task_id=task.id,
        status="pending",
        message="XML export started",
    )


# ═══════════════════════════════════════════════════════════════════════════
# VACANCY CRUD
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/vacancies", response_model=VacancyListResponse)
async def list_vacancies(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    city: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List vacancies with optional filtering."""
    # Validate pagination
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 50
    
    offset = (page - 1) * per_page
    
    # Build query
    query = select(Vacancy)
    
    # Apply filters
    if status:
        try:
            status_enum = VacancyStatus(status)
            query = query.where(Vacancy.status == status_enum)
        except ValueError:
            # Invalid status value, ignore filter
            pass
    
    if city:
        query = query.where(Vacancy.city.ilike(f"%{city}%"))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()
    
    # Get paginated results
    query = query.order_by(Vacancy.created_at.desc()).offset(offset).limit(per_page)
    result = await session.execute(query)
    vacancies = result.scalars().all()
    
    # Convert to response models
    items = [VacancyResponse.from_orm(vacancy) for vacancy in vacancies]
    
    return VacancyListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@app.get("/vacancies/{vacancy_id}", response_model=VacancyResponse)
async def get_vacancy(
    vacancy_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single vacancy by ID."""
    result = await session.execute(
        select(Vacancy).where(Vacancy.id == vacancy_id)
    )
    vacancy = result.scalar_one_or_none()
    
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    
    return VacancyResponse.from_orm(vacancy)


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of an async task."""
    from services.shared.celery_app import celery_app
    
    result = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
