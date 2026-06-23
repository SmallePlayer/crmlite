from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Role
from app.auth import hash_password, verify_password, create_access_token, get_current_user, require_admin
from app.audit import log

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginData(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role_id: int
    full_name: str = ""


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    role_id: int
    role_name: Optional[str] = None
    full_name: str
    is_active: bool

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    name: str
    can_view_clients: bool = True
    can_edit_clients: bool = False
    can_view_services: bool = True
    can_edit_services: bool = False
    can_view_orders: bool = True
    can_edit_orders: bool = False
    can_delete_orders: bool = False
    can_manage_users: bool = False


class RoleOut(BaseModel):
    id: int
    name: str
    can_view_clients: bool
    can_edit_clients: bool
    can_view_services: bool
    can_edit_services: bool
    can_view_orders: bool
    can_edit_orders: bool
    can_delete_orders: bool
    can_manage_users: bool

    class Config:
        from_attributes = True


@router.post("/login")
def login(data: LoginData, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(403, "Пользователь заблокирован")
    token = create_access_token(user.id, user.role_id)
    role_name = user.role.name if user.role else ""
    log(user, "login", "user", user.id, f"Вход в систему", db=db)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role_id": user.role_id,
            "role_name": role_name,
            "full_name": user.full_name,
        },
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    role_name = user.role.name if user.role else ""
    return {
        "id": user.id,
        "username": user.username,
        "role_id": user.role_id,
        "role_name": role_name,
        "full_name": user.full_name,
    }


class ChangePasswordData(BaseModel):
    current_password: str
    new_password: str


@router.put("/change-password")
def change_password(data: ChangePasswordData, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Неверный текущий пароль")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    log(user, "update", "user", user.id, "Смена пароля", db=db)
    return {"ok": True}


# ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (только админ) =====

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    users = db.query(User).all()
    result = []
    for u in users:
        result.append(UserOut(
            id=u.id,
            username=u.username,
            role_id=u.role_id,
            role_name=u.role.name if u.role else "",
            full_name=u.full_name,
            is_active=u.is_active,
        ))
    return result


@router.post("/users", response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(400, "Логин уже занят")
    role = db.query(Role).get(data.role_id)
    if not role:
        raise HTTPException(404, "Роль не найдена")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role_id=data.role_id,
        full_name=data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log(_, "create", "user", user.id, f"Создан пользователь {user.username}", db=db)
    return UserOut(
        id=user.id,
        username=user.username,
        role_id=user.role_id,
        role_name=user.role.name if user.role else "",
        full_name=user.full_name,
        is_active=user.is_active,
    )


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role_id is not None:
        role = db.query(Role).get(data.role_id)
        if not role:
            raise HTTPException(404, "Роль не найдена")
        user.role_id = data.role_id
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    log(_, "update", "user", user.id, f"Обновлён пользователь {user.username}", db=db)
    return UserOut(
        id=user.id,
        username=user.username,
        role_id=user.role_id,
        role_name=user.role.name if user.role else "",
        full_name=user.full_name,
        is_active=user.is_active,
    )


# ===== УПРАВЛЕНИЕ РОЛЯМИ (только админ) =====

@router.get("/roles", response_model=List[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()


@router.post("/roles", response_model=RoleOut)
def create_role(data: RoleCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(400, "Роль уже существует")
    role = Role(**data.model_dump())
    db.add(role)
    db.commit()
    db.refresh(role)
    log(_, "create", "role", role.id, f"Создана роль {role.name}", db=db)
    return role


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, data: RoleCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    role = db.query(Role).get(role_id)
    if not role:
        raise HTTPException(404, "Роль не найдена")
    for k, v in data.model_dump().items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    log(_, "update", "role", role.id, f"Обновлена роль {role.name}", db=db)
    return role


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    role = db.query(Role).get(role_id)
    if not role:
        raise HTTPException(404, "Роль не найдена")
    if role.name == "admin":
        raise HTTPException(400, "Нельзя удалить роль админа")
    db.delete(role)
    db.commit()
    log(_, "delete", "role", role_id, f"Удалена роль {role.name}", db=db)
    return {"ok": True}
