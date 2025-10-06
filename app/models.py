from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
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
    assigned_requests = relationship(
        "TranslationRequest", back_populates="translator", foreign_keys="TranslationRequest.translator_id"
    )


class TranslationRequest(Base):
    __tablename__ = "translation_requests"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    translator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source_language = Column(String, nullable=False)
    target_language = Column(String, nullable=False)
    status = Column(String, nullable=False, default="New")
    original_filename = Column(String, nullable=False)
    translated_filename = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("User", foreign_keys=[client_id], back_populates="translation_requests")
    translator = relationship("User", foreign_keys=[translator_id], back_populates="assigned_requests")
