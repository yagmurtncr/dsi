#!/usr/bin/env python3
"""
🛡️ RBAC (Role-Based Access Control)
Rol tabanlı erişim kontrolü - Kim neye erişebilir?

Roller:
- admin: Tüm yetkiler (kullanıcı yönetimi, sistem ayarları)
- user: Standart kullanıcı (generate, health)
- pilot: Sınırlı test erişimi (generate - düşük limit)
- readonly: Sadece okuma (health, status)
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from functools import wraps
from fastapi import HTTPException, Request
from datetime import datetime


class Role(str, Enum):
    """Kullanıcı rolleri"""
    ADMIN = "admin"
    USER = "user"
    PILOT = "pilot"
    READONLY = "readonly"


class Permission(str, Enum):
    """Sistem izinleri"""
    # Generate izinleri
    GENERATE = "generate"
    GENERATE_UNLIMITED = "generate_unlimited"
    
    # Sistem izinleri
    VIEW_HEALTH = "view_health"
    VIEW_SECURITY_STATUS = "view_security_status"
    VIEW_LOGS = "view_logs"
    
    # Yönetim izinleri
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_SETTINGS = "manage_settings"
    
    # PII izinleri
    VIEW_PII = "view_pii"  # Maskelenmemiş PII görme
    EXPORT_DATA = "export_data"


# Rol-İzin matrisi
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        Permission.GENERATE,
        Permission.GENERATE_UNLIMITED,
        Permission.VIEW_HEALTH,
        Permission.VIEW_SECURITY_STATUS,
        Permission.VIEW_LOGS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.MANAGE_SETTINGS,
        Permission.VIEW_PII,
        Permission.EXPORT_DATA,
    },
    Role.USER: {
        Permission.GENERATE,
        Permission.VIEW_HEALTH,
        Permission.VIEW_PII,  # 🆕 PII maskeleme kullanabilir
    },
    Role.PILOT: {
        Permission.GENERATE,  # Sınırlı (rate limit ile)
        Permission.VIEW_HEALTH,
        Permission.VIEW_PII,  # 🆕 PII maskeleme kullanabilir
    },
    Role.READONLY: {
        Permission.VIEW_HEALTH,
        Permission.VIEW_SECURITY_STATUS,
    },
}

# Endpoint-İzin eşleştirmesi
ENDPOINT_PERMISSIONS: Dict[str, Permission] = {
    "/generate": Permission.GENERATE,
    "/health": Permission.VIEW_HEALTH,
    "/security/status": Permission.VIEW_SECURITY_STATUS,
    "/security/public-key": Permission.VIEW_HEALTH,
    "/admin/users": Permission.MANAGE_USERS,
    "/admin/roles": Permission.MANAGE_ROLES,
    "/admin/settings": Permission.MANAGE_SETTINGS,
    "/admin/logs": Permission.VIEW_LOGS,
    "/gdpr/export-my-data": Permission.EXPORT_DATA,
}

# Rol bazlı rate limit çarpanları
ROLE_RATE_LIMITS: Dict[Role, Dict[str, int]] = {
    Role.ADMIN: {
        "generate": 1000,  # Sınırsıza yakın
        "default": 500,
    },
    Role.USER: {
        "generate": 30,
        "default": 100,
    },
    Role.PILOT: {
        "generate": 10,   # Sınırlı test
        "default": 30,
    },
    Role.READONLY: {
        "generate": 0,    # Generate izni yok
        "default": 50,
    },
}


class RBACManager:
    """
    🛡️ RBAC Yöneticisi
    
    Kullanıcı rollerini ve izinlerini yönetir.
    """
    
    def __init__(self):
        # Kullanıcı-rol eşleştirmesi (production'da DB'den gelir)
        self.user_roles: Dict[str, Role] = {
            "admin": Role.ADMIN,
            "yagmur": Role.USER,
            "pilot1": Role.PILOT,
            "guest": Role.READONLY,
        }
        
        # Özel kullanıcı izinleri (rol dışı ek izinler)
        self.user_extra_permissions: Dict[str, Set[Permission]] = {}
        
        # Geçici yetki yükseltmeleri
        self.temporary_elevations: Dict[str, Dict] = {}
        
        print("🛡️ RBAC Manager başlatıldı")
        print(f"   Tanımlı roller: {len(Role)} adet")
        print(f"   Kullanıcı sayısı: {len(self.user_roles)}")
    
    def get_user_role(self, username: str) -> Role:
        """Kullanıcının rolünü döner"""
        return self.user_roles.get(username, Role.READONLY)
    
    def set_user_role(self, username: str, role: Role) -> bool:
        """Kullanıcıya rol atar"""
        self.user_roles[username] = role
        print(f"🛡️ Rol atandı: {username} → {role.value}")
        return True
    
    def get_user_permissions(self, username: str) -> Set[Permission]:
        """
        Kullanıcının tüm izinlerini döner
        (Rol izinleri + Özel izinler)
        """
        role = self.get_user_role(username)
        permissions = ROLE_PERMISSIONS.get(role, set()).copy()
        
        # Özel izinleri ekle
        if username in self.user_extra_permissions:
            permissions.update(self.user_extra_permissions[username])
        
        # Geçici yetki yükseltmesi kontrolü
        if username in self.temporary_elevations:
            elevation = self.temporary_elevations[username]
            if datetime.now() < elevation["expires"]:
                permissions.update(elevation["permissions"])
            else:
                # Süresi dolmuş, temizle
                del self.temporary_elevations[username]
        
        return permissions
    
    def has_permission(self, username: str, permission: Permission) -> bool:
        """Kullanıcının belirli bir izni var mı?"""
        permissions = self.get_user_permissions(username)
        return permission in permissions
    
    def check_endpoint_access(self, username: str, endpoint: str) -> tuple[bool, str]:
        """
        Kullanıcının endpoint'e erişim izni var mı?
        
        Returns:
            tuple[bool, str]: (İzin var mı, Hata mesajı)
        """
        # Endpoint için gerekli izni bul
        required_permission = ENDPOINT_PERMISSIONS.get(endpoint)
        
        if required_permission is None:
            # Tanımsız endpoint - varsayılan olarak izin ver (public)
            return True, "OK"
        
        # Kullanıcının izni var mı?
        if self.has_permission(username, required_permission):
            return True, "OK"
        
        role = self.get_user_role(username)
        return False, f"Erişim reddedildi. Rolünüz ({role.value}) bu işlem için yetkili değil."
    
    def get_rate_limit(self, username: str, endpoint_type: str = "default") -> int:
        """Kullanıcının rol bazlı rate limit'ini döner"""
        role = self.get_user_role(username)
        limits = ROLE_RATE_LIMITS.get(role, ROLE_RATE_LIMITS[Role.READONLY])
        return limits.get(endpoint_type, limits["default"])
    
    def grant_temporary_elevation(
        self, 
        username: str, 
        permissions: Set[Permission],
        duration_minutes: int = 30
    ):
        """
        Geçici yetki yükseltmesi
        (Örn: Admin onayı ile pilot'a 30 dakikalık unlimited generate)
        """
        from datetime import timedelta
        
        self.temporary_elevations[username] = {
            "permissions": permissions,
            "expires": datetime.now() + timedelta(minutes=duration_minutes),
            "granted_at": datetime.now()
        }
        
        print(f"⬆️ Geçici yetki: {username} → {[p.value for p in permissions]} ({duration_minutes}dk)")
    
    def revoke_temporary_elevation(self, username: str):
        """Geçici yetki yükseltmesini iptal et"""
        if username in self.temporary_elevations:
            del self.temporary_elevations[username]
            print(f"⬇️ Geçici yetki iptal: {username}")
    
    def add_user(self, username: str, role: Role = Role.USER) -> bool:
        """Yeni kullanıcı ekle"""
        if username in self.user_roles:
            return False
        
        self.user_roles[username] = role
        print(f"👤 Kullanıcı eklendi: {username} (rol: {role.value})")
        return True
    
    def remove_user(self, username: str) -> bool:
        """Kullanıcıyı sil"""
        if username not in self.user_roles:
            return False
        
        del self.user_roles[username]
        
        # İlgili özel izinleri de temizle
        if username in self.user_extra_permissions:
            del self.user_extra_permissions[username]
        
        if username in self.temporary_elevations:
            del self.temporary_elevations[username]
        
        print(f"🗑️ Kullanıcı silindi: {username}")
        return True
    
    def get_all_users(self) -> Dict[str, str]:
        """Tüm kullanıcıları ve rollerini döner"""
        return {user: role.value for user, role in self.user_roles.items()}
    
    def get_role_info(self, role: Role) -> Dict:
        """Rol hakkında detaylı bilgi döner"""
        permissions = ROLE_PERMISSIONS.get(role, set())
        rate_limits = ROLE_RATE_LIMITS.get(role, {})
        
        return {
            "role": role.value,
            "permissions": [p.value for p in permissions],
            "rate_limits": rate_limits,
            "user_count": sum(1 for r in self.user_roles.values() if r == role)
        }


# Singleton instance
_rbac_manager = None


def get_rbac_manager() -> RBACManager:
    """RBAC Manager singleton"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def require_permission(permission: Permission):
    """
    🔐 Permission decorator - Endpoint'leri korur
    
    Kullanım:
        @app.get("/admin/users")
        @require_permission(Permission.MANAGE_USERS)
        async def get_users(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # token_data'yı kwargs'tan al
            token_data = kwargs.get("token_data", {})
            username = token_data.get("sub", "unknown")
            
            rbac = get_rbac_manager()
            
            if not rbac.has_permission(username, permission):
                role = rbac.get_user_role(username)
                raise HTTPException(
                    status_code=403,
                    detail=f"Erişim reddedildi. Rolünüz ({role.value}) '{permission.value}' izni için yetkili değil."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(required_role: Role):
    """
    🔐 Role decorator - Minimum rol gereksinimi
    
    Kullanım:
        @app.get("/admin/settings")
        @require_role(Role.ADMIN)
        async def get_settings(...):
            ...
    """
    # Rol hiyerarşisi (yüksekten düşüğe)
    role_hierarchy = [Role.ADMIN, Role.USER, Role.PILOT, Role.READONLY]
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            token_data = kwargs.get("token_data", {})
            username = token_data.get("sub", "unknown")
            
            rbac = get_rbac_manager()
            user_role = rbac.get_user_role(username)
            
            # Hiyerarşi kontrolü
            user_level = role_hierarchy.index(user_role) if user_role in role_hierarchy else len(role_hierarchy)
            required_level = role_hierarchy.index(required_role)
            
            if user_level > required_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"Erişim reddedildi. Minimum rol gereksinimi: {required_role.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

