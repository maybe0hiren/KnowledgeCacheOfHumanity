from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth.auth_manager import signup, login, logout, get_user_from_token, forgot_password, change_password

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    username: str


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/signup")
async def signup_route(body: SignupRequest):
    result = signup(body.username, body.email, body.password)
    if not result["success"]:
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(content=result)


@router.post("/login")
async def login_route(body: LoginRequest):
    result = login(body.username, body.password)
    if not result["success"]:
        return JSONResponse(status_code=401, content=result)
    return JSONResponse(content={
        "success": True,
        "token": result["token"],
        "username": result["username"],
        "must_change_password": result.get("must_change_password", False),
    })


@router.post("/logout")
async def logout_route(request: Request):
    token = _extract_token(request)
    if token:
        logout(token)
    return JSONResponse(content={"success": True})


@router.get("/me")
async def me_route(request: Request):
    token = _extract_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})
    user = get_user_from_token(token)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Session expired"})
    return JSONResponse(content=user)


@router.post("/forgot-password")
async def forgot_password_route(body: ForgotPasswordRequest):
    result = forgot_password(body.username)
    if not result["success"]:
        return JSONResponse(status_code=404, content=result)
    return JSONResponse(content=result)


@router.post("/change-password")
async def change_password_route(request: Request, body: ChangePasswordRequest):
    token = _extract_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"error": "Not logged in"})
    result = change_password(token, body.new_password)
    if not result["success"]:
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(content=result)


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("session_token")
