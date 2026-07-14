from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Printer(Base):
    __tablename__ = "printers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PrintJob(Base):
    __tablename__ = "print_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    filament_id: Mapped[int] = mapped_column(ForeignKey("filaments.id"), index=True)
    filament = relationship("Filament")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    creator = relationship("User")
    grams: Mapped[int] = mapped_column(Integer, default=0)
    hours: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    waste_grams: Mapped[int] = mapped_column(Integer, default=0)
    printer_name: Mapped[str] = mapped_column(String(200), default="")
    weight_good: Mapped[int] = mapped_column(Integer, default=0)
    weight_waste: Mapped[int] = mapped_column(Integer, default=0)
    slicer_estimate: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
