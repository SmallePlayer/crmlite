from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Filament(Base):
    __tablename__ = "filaments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    article: Mapped[str] = mapped_column(String(100), default="")
    manufacturer: Mapped[str] = mapped_column(String(100), default="")
    type: Mapped[str] = mapped_column(String(50), default="PLA")
    color: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    grams_per_spool: Mapped[int] = mapped_column(Integer, default=1000)
    min_stock: Mapped[int] = mapped_column(Integer, default=500)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    movements = relationship("FilamentMovement", back_populates="filament",
                             order_by="FilamentMovement.id")


class FilamentMovement(Base):
    __tablename__ = "filament_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    filament_id: Mapped[int] = mapped_column(ForeignKey("filaments.id"), index=True)
    filament = relationship("Filament", back_populates="movements")
    type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(500), default="")
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
