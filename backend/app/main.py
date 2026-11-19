import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .keitaro import KeitaroClient, KeitaroError
from .models import Campaign

router = APIRouter()


def _error(e: KeitaroError):
    raise HTTPException(status_code=e.status or 502, detail=str(e))


def _offers_stream(streams: list[dict]) -> dict:
    for s in streams:
        # Офферный поток: содержит офферы и не редиректит на Google
        if s.get("offers"):
            return s
    raise HTTPException(status_code=404, detail="Офферный поток не найден")


def _equal_shares(n: int) -> list[int]:
    """Распределить 100% поровну, остаток — первым офферам."""
    base = 100 // n
    rest = 100 - base * n
    return [base + (1 if i < rest else 0) for i in range(n)]


def _stream_payload(stream: dict, offers: list[dict]) -> dict:
    """Собрать тело PUT /streams/{id} с переданным списком офферов."""
    return {
        "id": stream["id"],
        "name": stream.get("name", ""),
        "type": stream.get("type", "regular"),
        "schema": stream.get("schema", "landings"),
        "action_type": stream.get("action_type", "do_nothing"),
        "action_payload": stream.get("action_payload", ""),
        "state": stream.get("state", "active"),
        "collect_clicks": stream.get("collect_clicks", True),
        "filter_or": stream.get("filter_or", False),
        "weight": stream.get("weight", 0),
        "position": stream.get("position", 0),
        "filters": stream.get("filters", []),
        "triggers": stream.get("triggers", []),
        "landings": stream.get("landings", []),
        "offers": offers,
    }


# --- справочники для фронтенда ---


@router.get("/meta")
async def meta():
    k = KeitaroClient()
    try:
        domains, offers, groups = await k.list_domains(), await k.list_offers(), await k.list_groups()
    except KeitaroError as e:
        _error(e)
    return {
        "domains": [
            {"id": d["id"], "name": d.get("name"), "state": d.get("state")} for d in domains
        ],
        "offers": [
            {
                "id": o["id"],
                "name": o.get("name"),
                "state": o.get("state"),
                "country": o.get("country") or [],
            }
            for o in offers
        ],
        "groups": [{"id": g["id"], "name": g.get("name")} for g in groups],
    }


# --- создаватор кампаний ---


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: str = Field(min_length=2, max_length=2, description="Код страны, напр. DE")
    offer_id: int


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)):
    k = KeitaroClient()
    try:
        offer = next((o for o in await k.list_offers() if o["id"] == body.offer_id), None)
        if not offer:
            raise HTTPException(status_code=400, detail=f"Оффер {body.offer_id} не найден в Keitaro")
        group = await k.ensure_group()
        domain = await k.pick_domain()
        source = await k.pick_traffic_source()
        alias = f"{body.name[:40]}-{body.geo.lower()}"

        payload = {
            "name": body.name,
            "alias": alias,
            "group_id": group["id"],
            "domain_id": domain["id"],
            "traffic_source_id": source["id"] if source else 0,
            "state": "active",
            "streams": [
                {
                    "name": f"{body.geo.upper()} → Google",
                    "type": "regular",
                    "schema": "redirect",
                    "action_type": "http",
                    "action_payload": "https://google.com",
                    "state": "active",
                    "collect_clicks": True,
                    "filters": [{"name": "country", "mode": "accept", "payload": [body.geo.upper()]}],
                    "offers": [],
                    "landings": [],
                    "triggers": [],
                    "weight": 0,
                },
                {
                    "name": "Офферы",
                    "type": "regular",
                    "schema": "landings",
                    "action_type": "do_nothing",
                    "state": "active",
                    "collect_clicks": True,
                    "filters": [],
                    "landings": [],
                    "triggers": [],
                    "weight": 0,
                    "offers": [{"offer_id": body.offer_id, "share": 100}],
                },
            ],
        }
        created = None
        # Keitaro требует уникальные name/alias — при конфликте повторяем со случайным суффиксом
        for attempt in range(3):
            try:
                payload_try = dict(payload)
                payload_try["name"] = payload["name"] if attempt == 0 else f"{payload['name']} {secrets.token_hex(4)}"
                payload_try["alias"] = payload["alias"] if attempt == 0 else f"{payload['alias']}-{secrets.token_hex(4)}"
                created = await k.create_campaign(payload_try)
                break
            except KeitaroError as e:
                if "used" in str(e).lower() and attempt < 2:
                    continue
                raise
    except KeitaroError as e:
        _error(e)

    row = Campaign(
        id=created["id"],
        name=created.get("name") or body.name,
        alias=created.get("alias") or alias,
        geo=body.geo.upper(),
        offer_ids=str(body.offer_id),
        group_id=group["id"],
        domain_id=domain["id"],
        traffic_source_id=source["id"] if source else None,
    )
    db.merge(row)
    db.commit()

    streams = await k.get_streams(created["id"])
    return {"campaign": created, "streams": streams, "domain": domain, "group": group}


@router.get("/campaigns")
async def list_campaigns():
    k = KeitaroClient()
    try:
        campaigns = await k.list_campaigns()
    except KeitaroError as e:
        _error(e)
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "alias": c.get("alias"),
            "state": c.get("state"),
            "group": c.get("group") or "",
            "domain": c.get("domain"),
            "created_at": c.get("created_at"),
        }
        for c in campaigns
        if c.get("state") != "deleted"
    ]


# --- редактор кампании ---


@router.get("/campaigns/{campaign_id}/streams")
async def campaign_streams(campaign_id: int):
    k = KeitaroClient()
    try:
        campaign = await k.get_campaign(campaign_id)
        streams = await k.get_streams(campaign_id)
    except KeitaroError as e:
        _error(e)
    return {
        "campaign": {
            "id": campaign["id"],
            "name": campaign.get("name"),
            "alias": campaign.get("alias"),
            "state": campaign.get("state"),
            "group": campaign.get("group") or "",
            "domain": campaign.get("domain"),
        },
        "streams": [
            {
                "id": s["id"],
                "name": s.get("name"),
                "schema": s.get("schema"),
                "action_type": s.get("action_type"),
                "action_payload": s.get("action_payload"),
                "state": s.get("state"),
                "filters": s.get("filters", []),
                "offers": [
                    {"offer_id": o["offer_id"], "share": o.get("share", 0), "state": o.get("state")}
                    for o in s.get("offers", [])
                ],
            }
            for s in streams
        ],
    }


class OfferAdd(BaseModel):
    offer_id: int


@router.post("/campaigns/{campaign_id}/streams/{stream_id}/offers")
async def add_offer(campaign_id: int, stream_id: int, body: OfferAdd):
    k = KeitaroClient()
    try:
        if not await k.offer_exists(body.offer_id):
            raise HTTPException(status_code=400, detail=f"Оффер {body.offer_id} не найден в Keitaro")
        streams = await k.get_streams(campaign_id)
        stream = next((s for s in streams if s["id"] == stream_id), None)
        if not stream:
            raise HTTPException(status_code=404, detail="Поток не найден")
        offers = [{"offer_id": o["offer_id"], "share": o.get("share", 0)} for o in stream.get("offers", [])]
        if any(o["offer_id"] == body.offer_id for o in offers):
            raise HTTPException(status_code=400, detail="Этот оффер уже добавлен в поток")
        offers.append({"offer_id": body.offer_id, "share": 0})
        shares = _equal_shares(len(offers))
        for o, share in zip(offers, shares):
            o["share"] = share
        updated = await k.update_stream(stream_id, _stream_payload(stream, offers))
    except KeitaroError as e:
        _error(e)
    return {
        "stream_id": stream_id,
        "offers": [{"offer_id": o["offer_id"], "share": o.get("share", 0)} for o in updated.get("offers", [])],
    }


@router.delete("/campaigns/{campaign_id}/streams/{stream_id}/offers/{offer_id}")
async def remove_offer(campaign_id: int, stream_id: int, offer_id: int):
    k = KeitaroClient()
    try:
        streams = await k.get_streams(campaign_id)
        stream = next((s for s in streams if s["id"] == stream_id), None)
        if not stream:
            raise HTTPException(status_code=404, detail="Поток не найден")
        offers = [
            {"offer_id": o["offer_id"], "share": o.get("share", 0)}
            for o in stream.get("offers", [])
            if o["offer_id"] != offer_id
        ]
        if len(offers) == len(stream.get("offers", [])):
            raise HTTPException(status_code=404, detail="Оффер не найден в потоке")
        if offers:
            shares = _equal_shares(len(offers))
            for o, share in zip(offers, shares):
                o["share"] = share
        updated = await k.update_stream(stream_id, _stream_payload(stream, offers))
    except KeitaroError as e:
        _error(e)
    return {
        "stream_id": stream_id,
        "offers": [{"offer_id": o["offer_id"], "share": o.get("share", 0)} for o in updated.get("offers", [])],
    }
