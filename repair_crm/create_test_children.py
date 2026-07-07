#!/usr/bin/env python3
"""Скрипт для создания тестовых данных parent-child товаров"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from database import engine
from models.warehouse import Product

def create_test_data():
    with Session(engine) as session:
        # Создаём родительский товар (выходит из производства)
        parent = Product(
            name="Комплект переходников (снимается с производства)",
            article="ADAPTER-SET-OLD",
            color="Серебристый",
            quantity=10,
            cost_price=500,
            print_cost=100,
            pack_cost=50,
        )
        session.add(parent)
        session.flush()
        
        # Создаём дочерние товары (варианты комплекта)
        children = [
            Product(
                name="Комплект переходников - 1 шт",
                article="ADAPTER-1",
                color="Серебристый",
                quantity=5,
                cost_price=500,
                print_cost=100,
                pack_cost=50,
                parent_id=parent.id,
            ),
            Product(
                name="Комплект переходников - 2 шт",
                article="ADAPTER-2",
                color="Серебристый",
                quantity=3,
                cost_price=1000,
                print_cost=200,
                pack_cost=100,
                parent_id=parent.id,
            ),
            Product(
                name="Комплект переходников - 3 шт",
                article="ADAPTER-3",
                color="Серебристый",
                quantity=2,
                cost_price=1500,
                print_cost=300,
                pack_cost=150,
                parent_id=parent.id,
            ),
        ]
        
        for child in children:
            session.add(child)
        
        session.commit()
        print(f"✓ Создан родительский товар: {parent.name} (ID: {parent.id})")
        print(f"✓ Создано {len(children)} дочерних товаров:")
        for child in children:
            print(f"  - {child.name} (артикул: {child.article})")

if __name__ == "__main__":
    create_test_data()
