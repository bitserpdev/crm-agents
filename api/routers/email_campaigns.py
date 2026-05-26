import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

class EmailCampaignCreate(BaseModel):
    campaign_name: str
    service_description: Optional[str] = None
    from_address: str
    filter_region: Optional[str] = None
    filter_industry: Optional[str] = None
    filter_company_size: Optional[str] = None
    filter_min_score: Optional[int] = 0
    filter_max_score: Optional[int] = 100
    filter_stage: Optional[str] = None
    scheduled_at: Optional[datetime] = None

@router.get("")
def list_email_campaigns():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT campaign_id, campaign_name, campaign_status, from_address,
                   filter_region, filter_industry, filter_company_size,
                   filter_min_score, filter_max_score, filter_stage,
                   scheduled_at, created_at
            FROM crm.crm_campaigns
            WHERE campaign_type = 'email'
            ORDER BY created_at DESC
        """)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

@router.post("")
def create_email_campaign(payload: EmailCampaignCreate):
    # Get system user id
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("SELECT user_id FROM crm.crm_users LIMIT 1")
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=500, detail="No system user found")
        user_id = user["user_id"]

        status = "scheduled" if payload.scheduled_at else "draft"

        cur.execute("""
            INSERT INTO crm.crm_campaigns (
                campaign_name, campaign_type, campaign_status,
                from_address, service_description,
                filter_region, filter_industry, filter_company_size,
                filter_min_score, filter_max_score, filter_stage,
                scheduled_at, schedule_type, created_by
            ) VALUES (
                %s, 'email', %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            RETURNING *
        """, (
            payload.campaign_name, status,
            payload.from_address, payload.service_description,
            payload.filter_region, payload.filter_industry, payload.filter_company_size,
            payload.filter_min_score, payload.filter_max_score, payload.filter_stage,
            payload.scheduled_at, "scheduled" if payload.scheduled_at else "immediate",
            user_id
        ))
        conn.commit()
        return cur.fetchone()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/{campaign_id}")
def delete_email_campaign(campaign_id: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM crm.crm_campaigns WHERE campaign_id = %s AND campaign_type = 'email'",
            (campaign_id,)
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return {"deleted": campaign_id}
    finally:
        cur.close()
        conn.close()
