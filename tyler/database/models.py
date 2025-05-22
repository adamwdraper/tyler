import json
from sqlalchemy.types import TypeDecorator, TEXT, JSON

"""Database models for SQLAlchemy"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

class JSONBCompat(TypeDecorator):
    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if dialect.name == 'postgresql':
            return value
        if value is not None:
            return value
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == 'postgresql':
            return value
        if value is not None:
            return value
        return value

Base = declarative_base()

class ThreadRecord(Base):
    __tablename__ = 'threads'
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    attributes = Column(JSONBCompat, nullable=False, default={})
    platforms = Column(JSONBCompat, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    
    messages = relationship("MessageRecord", back_populates="thread", cascade="all, delete-orphan")

class MessageRecord(Base):
    __tablename__ = 'messages'
    
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey('threads.id', ondelete='CASCADE'), nullable=False)
    sequence = Column(Integer, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String, nullable=True)
    tool_call_id = Column(String, nullable=True)
    tool_calls = Column(JSONBCompat, nullable=True)
    attributes = Column(JSONBCompat, nullable=False, default={})
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    source = Column(JSONBCompat, nullable=True)
    platforms = Column(JSONBCompat, nullable=True)
    attachments = Column(JSONBCompat, nullable=True)
    metrics = Column(JSONBCompat, nullable=False, default={})
    reactions = Column(JSONBCompat, nullable=True)
    
    thread = relationship("ThreadRecord", back_populates="messages") 