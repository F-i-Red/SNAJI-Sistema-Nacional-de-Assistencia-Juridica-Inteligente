
from fastapi import APIRouter
from app.workflow.approval_system import ApprovalSystem

router = APIRouter()

approval = ApprovalSystem()

@router.post("/workflow/approve")
async def approve_case(payload: dict):

    actor = payload.get("actor")
    process_id = payload.get("process_id")

    return approval.approve(
        actor,
        process_id
    )
