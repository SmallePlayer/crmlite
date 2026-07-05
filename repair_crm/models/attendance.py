from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user = relationship("User")
    date_str: Mapped[str] = mapped_column(String(10), default="")
    check_in: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    check_out: Mapped[datetime | None] = mapped_column(DateTime, default=None, nullable=True)
    report: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user = relationship("User")
    date: Mapped[datetime] = mapped_column(DateTime)
    time_from: Mapped[str] = mapped_column(String(5))
    time_to: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
