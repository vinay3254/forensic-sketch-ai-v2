from fastapi import APIRouter, Depends

from backend.auth.deps import current_user
from backend.interview.questions import EXTRAS, FEATURES, FREE_RECALL
from backend.models import User

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.get("/questions")
def questions(user: User = Depends(current_user)):
    return {"free_recall": FREE_RECALL, "features": FEATURES, "extras": EXTRAS}
