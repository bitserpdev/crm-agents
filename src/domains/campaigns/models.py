from pydantic import BaseModel, Field
from typing import Optional, List, Any


class LinkedInFilters(BaseModel):
    industry:        Optional[str]  = None
    region:          Optional[str]  = None
    management_tier: Optional[str]  = None
    email:           Optional[bool] = False
    phone:           Optional[bool] = False
    domain:          Optional[str]  = None


class SourceConfig(BaseModel):
    type:              str                        # "linkedin" | "upwork" | future platforms
    linkedin_filters:  Optional[LinkedInFilters] = None
    filter_match_mode: Optional[str]             = "all"
    extra:             Optional[dict]            = Field(default_factory=dict)


class CampaignCreate(BaseModel):
    campaign_name:     str
    cron_expression:   str
    source_configs:    List[Any]
    is_active:         Optional[bool]            = True
    linkedin_filters:  Optional[LinkedInFilters] = None
    filter_match_mode: Optional[str]             = "all"


class CampaignUpdate(BaseModel):
    campaign_name:     Optional[str]             = None
    cron_expression:   Optional[str]             = None
    source_configs:    Optional[List[Any]]       = None
    is_active:         Optional[bool]            = None
    linkedin_filters:  Optional[LinkedInFilters] = None
    filter_match_mode: Optional[str]             = None


class FilterValidationRequest(BaseModel):
    industry:        Optional[str] = None
    region:          Optional[str] = None
    management_tier: Optional[str] = None
    domain:          Optional[str] = None


class FilterValidationResult(BaseModel):
    valid:  bool
    checks: dict