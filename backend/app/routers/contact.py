"""Contact form: title + description + small attachments, stored for admins to read."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import ContactMessage, User
from app.schemas import ContactIn

router = APIRouter(prefix="/api", tags=["contact"])

_MAX_FILES = 3
_MAX_B64 = 1_400_000  # ~1MB per file after base64


@router.post("/contact")
def submit_contact(req: ContactIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    atts = []
    for a in (req.attachments or [])[:_MAX_FILES]:
        data = a.get("data") or ""
        if len(data) > _MAX_B64:
            raise HTTPException(status_code=400, detail="Each attachment must be under ~1MB")
        atts.append({"name": a.get("name"), "type": a.get("type"), "data": data})
    db.add(ContactMessage(
        user_id=user.id, email=user.email, contact=(req.contact or None),
        title=req.title[:256], description=req.description, attachments=atts,
    ))
    db.commit()
    return {"ok": True}
