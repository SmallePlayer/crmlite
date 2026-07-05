from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    client = relationship("Client", back_populates="orders")
    order_type: Mapped[str] = mapped_column(String(20), default="repair")
    printer: Mapped[str] = mapped_column(String(200))
    defect: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    total_price: Mapped[float] = mapped_column(Float, default=0)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    assignee = relationship("User")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
    schedule_location: Mapped[str] = mapped_column(String(300), default="")
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    warranty_days: Mapped[int] = mapped_column(Integer, default=0)
    is_warranty: Mapped[bool] = mapped_column(Boolean, default=False)
    prepaid: Mapped[float] = mapped_column(Float, default=0)
    estimated_price: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(100), default="")
    items = relationship(
        "OrderItem", back_populates="order",
        cascade="all, delete-orphan", order_by="OrderItem.id",
    )
    parts = relationship(
        "OrderPart", back_populates="order",
        cascade="all, delete-orphan", order_by="OrderPart.id",
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order = relationship("Order", back_populates="items")
    name: Mapped[str] = mapped_column(String(300))
    price: Mapped[float] = mapped_column(Float, default=0)


class OrderPart(Base):
    __tablename__ = "order_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order = relationship("Order", back_populates="parts")
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    part = relationship("Part")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0)
