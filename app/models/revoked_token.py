from sqlalchemy import Column, DateTime, Integer, String
from app.core.database import Base
from app.core.datetime_utils import utc_now


class RevokedToken(Base):
    """Stores invalidated JWT tokens and JTIs (Token Blacklist)."""
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    jti = Column(String(64), index=True, nullable=True)
    revoked_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<RevokedToken id={self.id} jti={self.jti}>"
