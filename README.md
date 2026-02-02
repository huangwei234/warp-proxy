# Warp API Proxy - Render 部署指南

## 快速部署

### 1. 注册 Render.com
访问 https://render.com 注册账号（可用 GitHub 登录）

### 2. 创建 Web Service
1. 点击 "New" -> "Web Service"
2. 选择 "Build and deploy from a Git repository"
3. 连接你的 GitHub 仓库（需要先把这个文件夹推送到 GitHub）

### 3. 配置
- **Name**: warp-api-proxy
- **Region**: Oregon (US West) 或 Singapore
- **Branch**: main
- **Root Directory**: render-deploy
- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 4. 环境变量
添加环境变量 `WARP_ACCOUNTS`，值为你的账号 JSON（或上传 accounts.json 文件）

### 5. 部署
点击 "Create Web Service"，等待部署完成

## 使用

部署完成后，你会得到一个 URL，如：
```
https://warp-api-proxy.onrender.com
```

在其他客户端使用：
```
Base URL: https://warp-api-proxy.onrender.com/v1
API Key: 任意值（不需要）
```

## 测试

```bash
curl https://warp-api-proxy.onrender.com/health
```
