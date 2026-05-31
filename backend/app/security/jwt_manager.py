
from datetime import datetime, timedelta
import jwt

SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION"

class JWTManager:

    def generate_token(self, user_id: str):

        payload = {
            "sub": user_id,
            "exp": datetime.utcnow() + timedelta(hours=8)
        }

        return jwt.encode(
            payload,
            SECRET_KEY,
            algorithm="HS256"
        )

    def verify_token(self, token: str):

        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )
