from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)

    translation_requests = relationship(
        "TranslationRequest", back_populates="client", foreign_keys="TranslationRequest.client_id"
    )
    assigned_jobs = relationship("Job", back_populates="translator", foreign_keys="Job.translator_id")
    messages = relationship("Message", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class TranslationRequest(Base):
    __tablename__ = "translation_requests"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    status = Column(String, nullable=False, default="New")
    original_filename = Column(String, nullable=False)
    translated_filename = Column(String, nullable=True)
    word_count = Column(Integer, default=0)
    source_text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("User", foreign_keys=[client_id], back_populates="translation_requests")
    quote = relationship("Quote", back_populates="request", uselist=False)
    job = relationship("Job", back_populates="request", uselist=False)
    terms = relationship(
        "Term",
        primaryjoin="TranslationRequest.client_id==Term.client_id",
        viewonly=True,
    )


class Rate(Base):
    __tablename__ = "rates"

    id = Column(Integer, primary_key=True, index=True)
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    unit_price = Column(Float, nullable=False)
    currency = Column(String, default="EUR")


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("translation_requests.id"), nullable=False)
    word_count = Column(Integer, nullable=False, default=0)
    unit_price = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="EUR")
    total = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False, default="Draft")
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("TranslationRequest", back_populates="quote")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("translation_requests.id"), nullable=False)
    translator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default="New")
    due_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    delivered_filename = Column(String, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    translated_text = Column(Text, nullable=True)
    manager_comment = Column(Text, nullable=True)

    request = relationship("TranslationRequest", back_populates="job")
    translator = relationship("User", foreign_keys=[translator_id], back_populates="assigned_jobs")
    messages = relationship("Message", back_populates="job", cascade="all, delete-orphan")
    invoice = relationship("Invoice", back_populates="job", uselist=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="messages")
    user = relationship("User", back_populates="messages")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="EUR")
    status = Column(String, nullable=False, default="Draft")
    issued_at = Column(DateTime, nullable=True)
    pdf_path = Column(String, nullable=True)

    client = relationship("User")
    job = relationship("Job", back_populates="invoice")


class Term(Base):
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_term = Column(String, nullable=False)
    target_term = Column(String, nullable=False)
    notes = Column(Text, nullable=True)

    client = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    object_type = Column(String, nullable=False)
    object_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="audit_logs")
