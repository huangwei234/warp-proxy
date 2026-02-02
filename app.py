#!/usr/bin/env python3
"""
Warp API Proxy - 部署到 Render.com
提供 OpenAI 兼容 API，使用你的账号池
"""
import os
import json
import asyncio
import httpx
import time
import base64
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Warp API Proxy")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 账号池
class AccountPool:
    def __init__(self):
        self.accounts = []
        self.current_index = 0
        self.jwt_cache = {}  # email -> (jwt, expire_time)
        self.load_accounts()
    
    def load_accounts(self):
        """从环境变量或文件加载账号"""
        # 优先从文件
        if os.path.exists("accounts.json"):
            with open("accounts.json", "r", encoding="utf-8") as f:
                self.accounts = json.load(f)
                print(f"Loaded {len(self.accounts)} accounts from file")
                return
        
        # 从环境变量（Base64 编码）
        accounts_b64 = os.getenv("WARP_ACCOUNTS_B64")
        if accounts_b64:
            try:
                accounts_json = base64.b64decode(accounts_b64).decode("utf-8")
                self.accounts = json.loads(accounts_json)
                print(f"Loaded {len(self.accounts)} accounts from env (base64)")
                return
            except Exception as e:
                print(f"Failed to load from WARP_ACCOUNTS_B64: {e}")
        
        print("No accounts loaded!")
    
    def get_next_account(self):
        """轮询获取下一个账号"""
        if not self.accounts:
            return None
        account = self.accounts[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.accounts)
        return account
    
    async def get_jwt(self, account):
        """获取 JWT token（带缓存）"""
        email = account.get("email", "")
        
        # 检查缓存
        if email in self.jwt_cache:
            jwt, expire_time = self.jwt_cache[email]
            if time.time() < expire_time - 300:  # 5分钟缓冲
                return jwt
        
        # 刷新 token
        refresh_token = account.get("refreshToken", "")
        if not refresh_token:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://app.warp.dev/proxy/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs",
                    headers={
                        "content-type": "application/x-www-form-urlencoded",
                        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
                    },
                    data=f"grant_type=refresh_token&refresh_token={refresh_token}"
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    jwt = data.get("access_token")
                    expires_in = data.get("expires_in", 3600)
                    self.jwt_cache[email] = (jwt, time.time() + expires_in)
                    print(f"Got JWT for {email}")
                    return jwt
                else:
                    print(f"Failed to refresh token for {email}: {resp.status_code}")
        except Exception as e:
            print(f"Refresh token error for {email}: {e}")
        
        return None

pool = AccountPool()


@app.get("/")
async def root():
    return {
        "service": "Warp API Proxy",
        "accounts": len(pool.accounts),
        "status": "ready" if pool.accounts else "no_accounts",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "test": "/test"
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok", "accounts": len(pool.accounts)}


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {"id": "claude-3-5-sonnet", "object": "model", "owned_by": "warp"},
            {"id": "gpt-4o", "object": "model", "owned_by": "warp"},
            {"id": "o1", "object": "model", "owned_by": "warp"},
        ]
    }


@app.get("/test")
async def test_connection():
    """测试账号和连接"""
    results = {
        "accounts_loaded": len(pool.accounts),
        "tests": []
    }
    
    if not pool.accounts:
        results["error"] = "No accounts loaded"
        return results
    
    # 测试第一个账号
    account = pool.accounts[0]
    email = account.get("email", "unknown")
    
    # 1. 测试 token 刷新
    jwt = await pool.get_jwt(account)
    if jwt:
        results["tests"].append({
            "name": "token_refresh",
            "status": "ok",
            "account": email,
            "jwt_preview": jwt[:50] + "..."
        })
    else:
        results["tests"].append({
            "name": "token_refresh", 
            "status": "failed",
            "account": email
        })
        return results
    
    # 2. 测试 AI 端点
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://app.warp.dev/ai/multi-agent",
                headers={
                    "authorization": f"Bearer {jwt}",
                    "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
                }
            )
            results["tests"].append({
                "name": "ai_endpoint",
                "status": "ok" if resp.status_code != 403 else "blocked",
                "http_status": resp.status_code
            })
    except Exception as e:
        results["tests"].append({
            "name": "ai_endpoint",
            "status": "error",
            "error": str(e)
        })
    
    return results


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容的聊天接口"""
    try:
        body = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")
    
    messages = body.get("messages", [])
    model = body.get("model", "claude-3-5-sonnet")
    stream = body.get("stream", False)
    
    # 获取账号和 JWT
    account = pool.get_next_account()
    if not account:
        raise HTTPException(500, "No accounts available")
    
    jwt = await pool.get_jwt(account)
    if not jwt:
        raise HTTPException(500, f"Failed to get JWT")
    
    # 构建请求
    # 注意：完整实现需要 protobuf 编码
    # 这里使用简化的 JSON 请求测试连通性
    
    headers = {
        "accept": "text/event-stream",
        "authorization": f"Bearer {jwt}",
        "content-type": "application/json",
        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
    }
    
    # 简化的测试响应
    # TODO: 需要实现完整的 protobuf 请求转换
    
    if stream:
        async def generate():
            yield 'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello from Warp Proxy! Account: ' + account.get("email", "") + '"}}]}\n\n'
            yield 'data: [DONE]\n\n'
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        return {
            "id": "test",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": f"Warp Proxy is working! Account: {account.get('email', '')}"
                }
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
