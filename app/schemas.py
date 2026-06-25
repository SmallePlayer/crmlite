from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class ClientCreate(BaseModel):
    full_name: str
    phone: str


class ClientOut(BaseModel):
    id: int
    full_name: str
    phone: str
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    name: str
    price: float
    category: str


class ServiceOut(BaseModel):
    id: int
    name: str
    price: float
    category: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrderItemIn(BaseModel):
    service_id: int
    custom_name: Optional[str] = None
    quantity: int = 1
    price: float


class OrderCreate(BaseModel):
    client_id: int
    client_name: str = ""
    order_type: str
    printer: Optional[str] = None
    description: Optional[str] = None
    complaint: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: List[OrderItemIn]
    materials: Optional[str] = None
    assigned_to: Optional[int] = None


class MaterialIn(BaseModel):
    product_id: int
    quantity: int


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    client_name: Optional[str] = None
    printer: Optional[str] = None
    description: Optional[str] = None
    complaint: Optional[str] = None
    work_done: Optional[str] = None
    parts_replaced: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: Optional[List[OrderItemIn]] = None
    materials: Optional[str] = None
    assigned_to: Optional[int] = None


class OrderItemOut(BaseModel):
    id: int
    service_id: int
    service_name: str
    custom_name: Optional[str] = None
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    client_id: int
    client_name: str
    order_type: str
    status: str
    printer: Optional[str]
    description: Optional[str]
    complaint: Optional[str]
    work_done: Optional[str]
    parts_replaced: Optional[str]
    modeler: Optional[str]
    address: Optional[str]
    pickup_time: Optional[str]
    total_price: float
    note: Optional[str]
    materials: Optional[str] = None
    assigned_to: Optional[int] = None
    assignee_name: Optional[str] = None
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True
