"""Link a Telegram account to the signed-in HR user or candidate.

HR routes use the HR session guard, candidate routes the candidate guard, so
neither kind of token can manage the other kind's link. The account is always
the caller; no account id is ever taken from the request.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.candidate_auth import get_current_candidate
from app.models.candidate_account import CandidateAccount
from app.models.user import User
from app.schemas.telegram import TelegramLinkStatus, TelegramLinkToken
from app.services.telegram import linking

router = APIRouter()


def _status(db: Session, owner: linking.Owner) -> TelegramLinkStatus:
    link = linking.get_link(db, owner)
    return TelegramLinkStatus(
        enabled=settings.telegram_configured,
        linked=link is not None,
        bot_username=settings.TELEGRAM_BOT_USERNAME or None,
        username=link.username if link else None,
        first_name=link.first_name if link else None,
        linked_at=link.linked_at if link else None,
        is_active=link.is_active if link else None,
    )


def _issue(db: Session, owner: linking.Owner) -> TelegramLinkToken:
    try:
        issued = linking.issue_link_token(db, owner)
    except linking.TelegramNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured",
        ) from None
    return TelegramLinkToken(deep_link=issued.deep_link, expires_at=issued.expires_at)


def _unlink(db: Session, owner: linking.Owner) -> Response:
    if not linking.unlink(db, owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram is not linked")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# HR workspace ---------------------------------------------------------------


@router.get("/hr/link", response_model=TelegramLinkStatus)
def hr_link_status(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TelegramLinkStatus:
    return _status(db, user)


@router.post("/hr/link-token", response_model=TelegramLinkToken)
def hr_link_token(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TelegramLinkToken:
    return _issue(db, user)


@router.delete("/hr/link", status_code=status.HTTP_204_NO_CONTENT)
def hr_unlink(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    return _unlink(db, user)


# Candidate Portal -----------------------------------------------------------


@router.get("/candidate/link", response_model=TelegramLinkStatus)
def candidate_link_status(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> TelegramLinkStatus:
    return _status(db, candidate)


@router.post("/candidate/link-token", response_model=TelegramLinkToken)
def candidate_link_token(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> TelegramLinkToken:
    return _issue(db, candidate)


@router.delete("/candidate/link", status_code=status.HTTP_204_NO_CONTENT)
def candidate_unlink(
    db: Session = Depends(get_db),
    candidate: CandidateAccount = Depends(get_current_candidate),
) -> Response:
    return _unlink(db, candidate)
