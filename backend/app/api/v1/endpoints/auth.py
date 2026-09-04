from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.auth import (ForgotPasswordRequest, ForgotPasswordResponse, LoginRequest,
                              MessageResponse, RegisterRequest, ResetPasswordRequest,
                              SessionResponse, UserSession)
from app.services.auth_service import AuthService

router = APIRouter()
COOKIE = "eva_refresh"


def _set_refresh(response: Response, token: str, request: Request):
    settings = request.app.state.settings
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.environment in {"staging", "production"},
                        samesite="lax", max_age=settings.refresh_token_days * 86400, path="/api/v1/auth")


@router.post("/login", response_model=SessionResponse)
async def login(payload: LoginRequest, response: Response, request: Request, session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    user, access, refresh = await AuthService(session, settings).login(payload.identifier.strip(), payload.password)
    _set_refresh(response, refresh, request)
    return SessionResponse(access_token=access, expires_in=settings.access_token_minutes * 60, user=user)


@router.post("/register", response_model=SessionResponse, status_code=201)
async def register(payload: RegisterRequest, response: Response, request: Request,
                   session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    user, access, refresh = await AuthService(session, settings).register(
        payload.username, payload.email, payload.password, payload.full_name
    )
    _set_refresh(response, refresh, request)
    return SessionResponse(access_token=access, expires_in=settings.access_token_minutes * 60, user=user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(payload: ForgotPasswordRequest, request: Request,
                          session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    token = await AuthService(session, settings).request_password_reset(payload.identifier)
    return ForgotPasswordResponse(
        message="If that account exists, password recovery instructions are ready.",
        reset_token=token if settings.environment in {"development", "test"} else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, request: Request,
                         session: AsyncSession = Depends(get_session)):
    await AuthService(session, request.app.state.settings).reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Your password has been reset. You can now sign in.")


@router.post("/refresh", response_model=SessionResponse)
async def refresh(response: Response, request: Request, eva_refresh: str = Cookie(default=""),
                  session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    user, access, replacement = await AuthService(session, settings).rotate(eva_refresh)
    _set_refresh(response, replacement, request)
    return SessionResponse(access_token=access, expires_in=settings.access_token_minutes * 60, user=user)


@router.get("/me", response_model=UserSession)
async def me(user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await session.get(User, user.id)


@router.post("/logout", status_code=204)
async def logout(response: Response, request: Request, eva_refresh: str | None = Cookie(default=None),
                 session: AsyncSession = Depends(get_session)):
    await AuthService(session, request.app.state.settings).logout(eva_refresh)
    response.delete_cookie(COOKIE, path="/api/v1/auth")
