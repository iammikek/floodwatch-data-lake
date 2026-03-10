from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class Station(BaseModel):
    id: str
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    river_name: Optional[str] = None
    provider: Optional[str] = None


class SeriesPoint(BaseModel):
    t: datetime
    value: float
    agg: str
    quality: Optional[str] = None


class MeasurementsResponse(BaseModel):
    station: Optional[Station] = None
    series: List[SeriesPoint]
    window: Dict[str, datetime]
    provenance: Dict[str, Any]


class RainfallDaily(BaseModel):
    date: date
    prcp_mm: float


class RainfallResponse(BaseModel):
    region_id: Optional[str] = None
    cell_id: Optional[str] = None
    series: List[RainfallDaily]
    provenance: Dict[str, Any]


class Warning(BaseModel):
    id: str
    severity: str
    title: str
    issued_at: datetime
    updated_at: datetime
    geometry: Optional[Dict[str, Any]] = None
    source: Optional[str] = None


class RetrieveContextResponse(BaseModel):
    signals: Dict[str, Any]
    snippets: List[Dict[str, Any]]
    window: Dict[str, datetime]


class ForecastDay(BaseModel):
    date: date
    summary: Optional[str] = None
    prcp_mm: Optional[float] = None
    wind_kph: Optional[float] = None


class ForecastResponse(BaseModel):
    region_id: str
    days: List[ForecastDay]
    provenance: Dict[str, Any]


class BackfillRequest(BaseModel):
    dataset: str
    region_id: Optional[str] = None
    series_id: Optional[str] = None
    from_: datetime
    to: datetime
    slice_size: Optional[str] = None


class BackfillAccepted(BaseModel):
    job_id: str
    status_url: str


class PolygonsResponse(BaseModel):
    region_id: str
    dataset: str
    scenario: Optional[str] = None
    format: str
    path: str
    count: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
