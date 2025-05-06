"""Database models for SQLAlchemy"""
from sqlalchemy import Column, String, JSON, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

Base = declarative_base()

class ThreadRecord(Base):
    __tablename__ = 'threads'
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    attributes = Column(JSON, nullable=False, default={})
    platforms = Column(JSON, nullable=True)
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
    tool_calls = Column(JSON, nullable=True)
    attributes = Column(JSON, nullable=False, default={})
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    source = Column(JSON, nullable=True)
    platforms = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=False, default={})
    reactions = Column(JSON, nullable=True)
    
    thread = relationship("ThreadRecord", back_populates="messages") 