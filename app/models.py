from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), default=0)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    role: Mapped[Optional["Role"]] = relationship("Role", back_populates="users")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    can_view_clients: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_clients: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_services: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_services: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_orders: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_orders: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_users: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_warehouse: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit_warehouse: Mapped[bool] = mapped_column(Boolean, default=False)
    can_assign_tasks: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="client", cascade="all, delete-orphan")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float, default=0)
    category: Mapped[str] = mapped_column(String(50))  # "repair" or "print"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="service", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"))
    order_type: Mapped[str] = mapped_column(String(50))  # "repair" or "print"
    status: Mapped[str] = mapped_column(String(50), default="active")
    client_name: Mapped[str] = mapped_column(String(255), default="")
    printer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    work_done: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parts_replaced: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modeler: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pickup_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_price: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    materials: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of {product_id, quantity}
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="orders")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to])
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"))
    custom_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    service: Mapped["Service"] = relationship("Service", back_populates="order_items")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String(50), default="шт")
    admin_controlled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    reports: Mapped[List["WorkReport"]] = relationship("WorkReport", back_populates="task")


class WorkReport(Base):
    __tablename__ = "work_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship("User")
    task: Mapped["Task"] = relationship("Task", back_populates="reports")
    order: Mapped[Optional["Order"]] = relationship("Order")


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))
    check_in: Mapped[str] = mapped_column(String(5))
    check_out: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    report_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship("User")


class OrderLog(Base):
    __tablename__ = "order_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    date: Mapped[str] = mapped_column(String(10))
    time_from: Mapped[str] = mapped_column(String(5))
    time_to: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped["User"] = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(255))  # create / update / delete / login / logout
    entity_type: Mapped[str] = mapped_column(String(100))  # client / order / service / role / user / task / report / lead
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(100), default="")
    article: Mapped[str] = mapped_column(String(255), default="", index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(50), default="sale")  # repair_part / sale
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(255), default="")
    type: Mapped[str] = mapped_column(String(50))  # supply / write-off
    reason: Mapped[str] = mapped_column(String(100))  # поставка / ozon / wb / другое
    quantity: Mapped[int] = mapped_column(Integer)  # положительное для supply, отрицательное для write-off
    stock_before: Mapped[int] = mapped_column(Integer, default=0)
    stock_after: Mapped[int] = mapped_column(Integer, default=0)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    product: Mapped["Product"] = relationship("Product")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    assigned_to: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(50), default="new")  # new / in_progress / done
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])
    assignee: Mapped["User"] = relationship("User", foreign_keys=[assigned_to])


class OrderComment(Base):
    __tablename__ = "order_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user_name: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    order: Mapped["Order"] = relationship("Order")


class OrderTemplate(Base):
    __tablename__ = "order_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    order_type: Mapped[str] = mapped_column(String(50))  # repair / print
    printer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modeler: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pickup_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    items: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of {service_id, custom_name, quantity, price}


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(50))
    service_type: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="new")  # new / contacted / converted / closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
