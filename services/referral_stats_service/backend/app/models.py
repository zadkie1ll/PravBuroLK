import uuid

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from .db import Base


class Client(Base):
    """Только поля, нужные для отображения имени и построения ref-ссылки —
    соответствует clients/models.py:Client."""

    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    middlename = Column(String(100), nullable=True)
    referral_code = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)


class Employee(Base):
    """Соответствует clients/models.py:Employee."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    referral_code = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)


class ReferralClick(Base):
    """Соответствует clients/models.py:ReferralClick. owner_content_type/owner_object_id
    (Django GenericForeignKey) сплющены в owner_type ('client'|'employee') + owner_id —
    без переноса Django ContentType framework."""

    __tablename__ = "referral_clicks"

    id = Column(Integer, primary_key=True)
    owner_type = Column(String(20), nullable=False)
    owner_id = Column(Integer, nullable=False)


class Application(Base):
    """Соответствует clients/models.py:Application — только поля для подсчёта заявок
    по владельцу реферальной ссылки."""

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    referral_owner_type = Column(String(20), nullable=True)
    referral_owner_id = Column(Integer, nullable=True)


class VisitEvent(Base):
    """Соответствует clients/models.py:DashboardVisit.visits — там это JSON-массив ISO-таймстемпов
    на одну запись (владелец+IP); здесь для подсчёта по периодам он расплющен в одну строку на
    визит (clients/views.py:dashboard_stats тоже просто считает по всем визитам, без привязки
    к владельцу)."""

    __tablename__ = "visit_events"

    id = Column(Integer, primary_key=True)
    visited_at = Column(DateTime(timezone=True), nullable=False)
