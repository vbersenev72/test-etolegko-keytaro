from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from .db import Base


class Campaign(Base):
    """Локальная копия кампаний, созданных через обёртку."""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)  # ID кампании в Keitaro
    name = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=False)
    geo = Column(String(8), nullable=False)
    offer_ids = Column(String(255), nullable=False, default="")  # список ID офферов через запятую
    group_id = Column(Integer, nullable=True)
    domain_id = Column(Integer, nullable=True)
    traffic_source_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
