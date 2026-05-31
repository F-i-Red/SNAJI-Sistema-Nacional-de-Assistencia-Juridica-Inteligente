
class AccessPolicy:

    def validate_access(
        self,
        user_role,
        process_visibility
    ):

        if process_visibility == "public":
            return True

        if user_role == "admin":
            return True

        if process_visibility == "institutional":
            return user_role in [
                "magistrado",
                "admin"
            ]

        return False
