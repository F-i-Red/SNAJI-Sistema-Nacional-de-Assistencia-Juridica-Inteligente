
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    MAGISTRADO = "magistrado"
    ADVOGADO = "advogado"
    ANALISTA = "analista"
    CIDADAO = "cidadao"

class RBACManager:

    ROLE_PERMISSIONS = {
        Role.ADMIN: ["*"],
        Role.MAGISTRADO: [
            "read_case",
            "write_case",
            "full_audit"
        ],
        Role.ADVOGADO: [
            "read_case",
            "submit_case"
        ],
        Role.ANALISTA: [
            "read_case"
        ],
        Role.CIDADAO: [
            "submit_case"
        ]
    }

    def has_permission(self, role, permission):

        permissions = self.ROLE_PERMISSIONS.get(role, [])

        return "*" in permissions or permission in permissions
