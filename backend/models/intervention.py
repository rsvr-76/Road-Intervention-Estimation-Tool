"""
Pydantic Models for Data Validation

This module defines Pydantic models for validating data structures
used throughout the brakes estimator application.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import JsonSchemaValue


class InterventionType(str, Enum):
    """Valid intervention types."""
    SPEED_BREAKER = "speed_breaker"
    RUMBLE_STRIP = "rumble_strip"
    ROAD_MARKING = "road_marking"
    SIGNAGE = "signage"
    GUARDRAIL = "guardrail"
    TRAFFIC_LIGHT = "traffic_light"
    PEDESTRIAN_CROSSING = "pedestrian_crossing"
    BARRIER = "barrier"
    PAVEMENT = "pavement"
    OTHER = "other"


class ExtractionMethod(str, Enum):
    """Valid extraction methods."""
    GEMINI = "gemini"
    OCR = "ocr"
    PDFPLUMBER = "pdfplumber"
    MANUAL = "manual"
    HYBRID = "hybrid"


class EstimateStatus(str, Enum):
    """Valid estimate statuses."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    PENDING = "pending"


class Intervention(BaseModel):
    """
    Model representing a road safety intervention.
    
    Attributes:
        type: Type of intervention (e.g., "speed_breaker")
        quantity: Quantity of the intervention
        unit: Unit of measurement (e.g., "units", "meters", "square_meters")
        location: Optional location description
        confidence: Confidence score between 0 and 1
        extraction_method: Method used to extract this data
    """
    
    type: str = Field(
        ...,
        description="Type of intervention",
        examples=["speed_breaker", "rumble_strip", "road_marking"]
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Quantity of the intervention (must be positive)"
    )
    unit: str = Field(
        ...,
        description="Unit of measurement",
        examples=["units", "meters", "square_meters", "linear_meters"]
    )
    location: Optional[str] = Field(
        None,
        description="Location or chainage information"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    extraction_method: str = Field(
        ...,
        description="Method used to extract the data",
        examples=["gemini", "ocr", "pdfplumber", "manual"]
    )
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate and normalize intervention type."""
        # Normalize to lowercase and replace spaces with underscores
        normalized = v.lower().strip().replace(" ", "_").replace("-", "_")
        
        # Check if it's a valid intervention type
        valid_types = [e.value for e in InterventionType]
        if normalized not in valid_types:
            # Allow custom types but log a warning
            pass
        
        return normalized
    
    @field_validator('extraction_method')
    @classmethod
    def validate_extraction_method(cls, v: str) -> str:
        """Validate extraction method."""
        normalized = v.lower().strip()
        valid_methods = [e.value for e in ExtractionMethod]
        
        if normalized not in valid_methods:
            raise ValueError(
                f"Invalid extraction_method '{v}'. "
                f"Valid methods are: {', '.join(valid_methods)}"
            )
        
        return normalized
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON string."""
        return super().model_dump_json(**kwargs)
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "speed_breaker",
                "quantity": 10,
                "unit": "units",
                "location": "Chainage 0+000 to 5+000",
                "confidence": 0.95,
                "extraction_method": "gemini"
            }
        }


class Material(BaseModel):
    """
    Model representing a construction material with pricing.
    
    Attributes:
        name: Name of the material
        quantity: Quantity required
        unit: Unit of measurement
        unit_price: Price per unit
        total_cost: Total cost (quantity × unit_price)
        irc_clause: IRC specification clause reference
        price_source: Source of price data (CPWD/GeM)
        fetched_date: Date when price was fetched
    """
    
    name: str = Field(
        ...,
        min_length=1,
        description="Name of the material"
    )
    quantity: float = Field(
        ...,
        gt=0,
        description="Quantity required (must be positive)"
    )
    unit: str = Field(
        ...,
        description="Unit of measurement"
    )
    unit_price: float = Field(
        ...,
        ge=0,
        description="Price per unit (must be non-negative)"
    )
    total_cost: float = Field(
        ...,
        ge=0,
        description="Total cost (quantity × unit_price)"
    )
    irc_clause: str = Field(
        ...,
        description="IRC specification clause reference",
        examples=["IRC:99-2018", "IRC:35-2015"]
    )
    price_source: str = Field(
        ...,
        description="Source of price data",
        examples=["CPWD", "GeM", "Market Rate"]
    )
    fetched_date: datetime = Field(
        default_factory=datetime.now,
        description="Date when price was fetched"
    )
    
    @model_validator(mode='after')
    def validate_total_cost(self) -> 'Material':
        """Validate that total_cost matches quantity × unit_price."""
        expected_total = round(self.quantity * self.unit_price, 2)
        actual_total = round(self.total_cost, 2)
        
        if abs(expected_total - actual_total) > 0.01:  # Allow small floating point differences
            raise ValueError(
                f"total_cost ({actual_total}) does not match "
                f"quantity ({self.quantity}) × unit_price ({self.unit_price}) = {expected_total}"
            )
        
        return self
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON string."""
        return super().model_dump_json(**kwargs)
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Bituminous Concrete",
                "quantity": 100,
                "unit": "cum",
                "unit_price": 5500.00,
                "total_cost": 550000.00,
                "irc_clause": "IRC:99-2018",
                "price_source": "CPWD",
                "fetched_date": "2025-11-17T10:30:00"
            }
        }


class EstimateItem(BaseModel):
    """
    Model representing a single item in an estimate.
    
    Attributes:
        intervention: The intervention details
        materials: List of materials required
        total_cost: Total cost for this item
        audit_trail: Audit information and processing metadata
        assumptions: List of assumptions made during estimation
    """
    
    intervention: Intervention = Field(
        ...,
        description="Intervention details"
    )
    materials: List[Material] = Field(
        default_factory=list,
        description="List of materials required"
    )
    total_cost: float = Field(
        ...,
        ge=0,
        description="Total cost for this estimate item"
    )
    audit_trail: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit information and processing metadata"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="List of assumptions made"
    )
    
    @model_validator(mode='after')
    def validate_total_cost(self) -> 'EstimateItem':
        """Validate that total_cost matches sum of material costs."""
        if self.materials:
            expected_total = round(sum(m.total_cost for m in self.materials), 2)
            actual_total = round(self.total_cost, 2)
            
            if abs(expected_total - actual_total) > 0.01:
                raise ValueError(
                    f"total_cost ({actual_total}) does not match "
                    f"sum of material costs ({expected_total})"
                )
        
        return self
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON string."""
        return super().model_dump_json(**kwargs)
    
    class Config:
        json_schema_extra = {
            "example": {
                "intervention": {
                    "type": "speed_breaker",
                    "quantity": 10,
                    "unit": "units",
                    "location": "Various locations",
                    "confidence": 0.95,
                    "extraction_method": "gemini"
                },
                "materials": [],
                "total_cost": 550000.00,
                "audit_trail": {
                    "processed_at": "2025-11-17T10:30:00",
                    "processor": "gemini-2.0-flash"
                },
                "assumptions": [
                    "Standard speed breaker dimensions assumed",
                    "Material rates from CPWD 2024"
                ]
            }
        }


class Estimate(BaseModel):
    """
    Model representing a complete estimate.
    
    Attributes:
        estimate_id: Unique identifier for the estimate
        filename: Original filename of uploaded document
        created_at: Timestamp when estimate was created
        status: Current status of the estimate
        items: List of estimate items
        total_cost: Total cost of all items
        confidence: Overall confidence score
        metadata: Additional metadata
    """
    
    estimate_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the estimate"
    )
    filename: str = Field(
        ...,
        min_length=1,
        description="Original filename"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Creation timestamp"
    )
    status: str = Field(
        default="processing",
        description="Current status"
    )
    items: List[EstimateItem] = Field(
        default_factory=list,
        description="List of estimate items"
    )
    total_cost: float = Field(
        default=0.0,
        ge=0,
        description="Total cost of all items"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence score"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate estimate status."""
        normalized = v.lower().strip()
        valid_statuses = [e.value for e in EstimateStatus]
        
        if normalized not in valid_statuses:
            raise ValueError(
                f"Invalid status '{v}'. "
                f"Valid statuses are: {', '.join(valid_statuses)}"
            )
        
        return normalized
    
    @model_validator(mode='after')
    def validate_total_cost(self) -> 'Estimate':
        """Validate that total_cost matches sum of item costs."""
        if self.items:
            expected_total = round(sum(item.total_cost for item in self.items), 2)
            actual_total = round(self.total_cost, 2)
            
            if abs(expected_total - actual_total) > 0.01:
                raise ValueError(
                    f"total_cost ({actual_total}) does not match "
                    f"sum of item costs ({expected_total})"
                )
        
        return self
    
    @model_validator(mode='after')
    def calculate_average_confidence(self) -> 'Estimate':
        """Calculate average confidence if not set."""
        if self.items and self.confidence == 0.0:
            avg_confidence = sum(
                item.intervention.confidence for item in self.items
            ) / len(self.items)
            self.confidence = round(avg_confidence, 2)
        
        return self
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON string."""
        return super().model_dump_json(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with serialized datetime objects."""
        data = self.model_dump()
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        for item in data.get('items', []):
            for material in item.get('materials', []):
                if isinstance(material.get('fetched_date'), datetime):
                    material['fetched_date'] = material['fetched_date'].isoformat()
        return data
    
    class Config:
        json_schema_extra = {
            "example": {
                "estimate_id": "EST-2025-001",
                "filename": "road_safety_audit.pdf",
                "created_at": "2025-11-17T10:30:00",
                "status": "completed",
                "items": [],
                "total_cost": 1500000.00,
                "confidence": 0.92,
                "metadata": {
                    "road_name": "NH-44",
                    "location": "Km 100-105",
                    "project_code": "PRJ-2025-001"
                }
            }
        }
