from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = "sqlite:///" + os.path.join(BACKEND_DIR, "fintel.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    document_type = Column(String(100))
    file_path = Column(String(1000))
    status = Column(String(50), default="uploaded")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    clauses = relationship(
        "Clause",
        back_populates="document",
        cascade="all, delete"
    )

    reports = relationship(
        "RiskReport",
        back_populates="document",
        cascade="all, delete"
    )


class Clause(Base):
    __tablename__ = "clauses"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False
    )
    clause_text = Column(Text, nullable=False)
    clause_number = Column(Integer)

    document = relationship(
        "Document",
        back_populates="clauses"
    )

    predictions = relationship(
        "RiskPrediction",
        back_populates="clause",
        cascade="all, delete"
    )


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True, index=True)
    clause_id = Column(
        Integer,
        ForeignKey("clauses.id"),
        nullable=False
    )
    risk_label = Column(String(100), nullable=False)
    confidence = Column(Float)
    model_name = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

    clause = relationship(
        "Clause",
        back_populates="predictions"
    )


class RiskReport(Base):
    __tablename__ = "risk_reports"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False
    )
    overall_risk = Column(String(50))
    risk_score = Column(Float)
    high_risk_count = Column(Integer, default=0)
    medium_risk_count = Column(Integer, default=0)
    low_risk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship(
        "Document",
        back_populates="reports"
    )


Base.metadata.create_all(bind=engine)

print("Fintel SQLite database initialized successfully.")