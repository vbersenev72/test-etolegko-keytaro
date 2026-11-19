from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings


class KeitaroError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class KeitaroClient:
    """Тонкий клиент Admin API Keitaro: {base_url}/admin_api/v1/..."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        s = get_settings()
        self.base_url = (base_url or s.keitaro_base_url).rstrip("/")
        self.api_url = f"{self.base_url}/admin_api/v1"
        self.api_key = api_key or s.keitaro_api_key

    def _headers(self) -> dict:
        return {"Api-Key": self.api_key, "Content-Type": "application/json"}

    async def request(self, method: str, path: str, json: Any | None = None, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method, f"{self.api_url}/{path.lstrip('/')}", headers=self._headers(), json=json, params=params
            )
            try:
                data = resp.json()
            except ValueError:
                raise KeitaroError(f"Некорректный ответ Keitaro (HTTP {resp.status_code})", resp.status_code)
            if resp.status_code >= 400:
                msg = data.get("error") if isinstance(data, dict) else None
                if isinstance(msg, dict):
                    msg = msg.get("message")
                msg = msg or str(data)[:300] or f"HTTP {resp.status_code}"
                raise KeitaroError(msg, resp.status_code)
            return data

    # --- ресурсы ---

    async def list_campaigns(self) -> list[dict]:
        return await self.request("GET", "campaigns")

    async def get_campaign(self, campaign_id: int) -> dict:
        return await self.request("GET", f"campaigns/{campaign_id}")

    async def create_campaign(self, payload: dict) -> dict:
        return await self.request("POST", "campaigns", json=payload)

    async def delete_campaign(self, campaign_id: int) -> dict:
        return await self.request("DELETE", f"campaigns/{campaign_id}")

    async def get_streams(self, campaign_id: int) -> list[dict]:
        return await self.request("GET", f"campaigns/{campaign_id}/streams")

    async def update_stream(self, stream_id: int, payload: dict) -> dict:
        return await self.request("PUT", f"streams/{stream_id}", json=payload)

    async def list_offers(self) -> list[dict]:
        return await self.request("GET", "offers", params={"limit": 1000})

    async def offer_exists(self, offer_id: int) -> bool:
        return any(o["id"] == offer_id for o in await self.list_offers())

    async def list_domains(self) -> list[dict]:
        return await self.request("GET", "domains")

    async def list_groups(self, type_: str = "campaigns") -> list[dict]:
        return await self.request("GET", "groups", params={"type": type_})

    async def create_group(self, name: str) -> dict:
        return await self.request("POST", "groups", json={"name": name, "type": "campaigns"})

    async def list_traffic_sources(self) -> list[dict]:
        return await self.request("GET", "traffic_sources")

    # --- бизнес-логика ---

    async def ensure_group(self, name: str | None = None) -> dict:
        """Найти группу по имени, при отсутствии — создать."""
        name = name or get_settings().group_name
        for g in await self.list_groups():
            if g.get("name") == name:
                return g
        return await self.create_group(name)

    async def pick_domain(self) -> dict:
        s = get_settings()
        domains = [d for d in await self.list_domains() if d.get("state") == "active"]
        for d in domains:
            if s.domain_name and d.get("name") == s.domain_name:
                return d
        if domains:
            return domains[0]
        raise KeitaroError("В Keitaro нет активных доменов")

    async def pick_traffic_source(self) -> dict | None:
        s = get_settings()
        sources = await self.list_traffic_sources()
        for src in sources:
            if s.traffic_source_name and src.get("name") == s.traffic_source_name:
                return src
        return sources[0] if sources else None
