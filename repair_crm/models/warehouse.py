from datetime import datetime
from sqlalchemy import String, Float, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Part(Base):
    __tablename__ = "parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    article: Mapped[str] = mapped_column(String(100), unique=True)
    purchase_price: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    movements = relationship("StockMovement", back_populates="part",
                             order_by="StockMovement.id")


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), index=True)
    part = relationship("Part", back_populates="movements")
    type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    price_per_unit: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(String(500), default="")
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    article: Mapped[str] = mapped_column(String(100), unique=True)
    color: Mapped[str] = mapped_column(String(100), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    cost_price: Mapped[float] = mapped_column(Float, default=0)
    print_cost: Mapped[float] = mapped_column(Float, default=0)
    pack_cost: Mapped[float] = mapped_column(Float, default=0)
    variants: Mapped[str] = mapped_column(Text, default="[]")
    image: Mapped[str] = mapped_column(String(300), default="")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    movements = relationship("ProductMovement", back_populates="product",
                             order_by="ProductMovement.id")
    parent = relationship("Product", remote_side=[id], backref="children")


class PackagingItem(Base):
    __tablename__ = "packaging_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(10), default="шт")
    price_per_unit: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProductPackaging(Base):
    __tablename__ = "product_packaging"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    packaging_item_id: Mapped[int] = mapped_column(ForeignKey("packaging_items.id"))
    quantity: Mapped[float] = mapped_column(Float, default=0)
    product = relationship("Product", backref="packaging_links")
    packaging_item = relationship("PackagingItem")


class ProductMovement(Base):
    __tablename__ = "product_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    product = relationship("Product", back_populates="movements")
    type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    destination: Mapped[str] = mapped_column(String(50), default="")
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
