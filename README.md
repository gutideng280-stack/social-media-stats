# 社交媒体互动数据统计工具

批量查询 X (Twitter)、Facebook、Instagram、Threads、哔哩哔哩、小红书的帖子互动数据（点赞、评论、转发/收藏等）。

## 功能特性

- **全自动获取**：X、Facebook、Instagram、Threads、哔哩哔哩
- **手动输入**：小红书（暂无公开 API）
- **批量查询**：一次添加多个链接，统一查询
- **结果导出**：支持导出 CSV 表格
- **跨平台部署**：前端可部署到 Vercel/Netlify，后端可部署到 Render

## 平台支持状态

| 平台 | 状态 | 说明 |
|------|------|------|
| X (Twitter) | 自动 | HTML 页面正则提取 |
| Facebook | 自动 | 需配置 cookies 文件 |
| Instagram | 自动 | 使用 instaloader |
| Threads | 自动 | 使用 Playwright |
| 哔哩哔哩 | 自动 | 官方 API |
| 小红书 | 手动 | 暂无可靠免登录方案 |

## 快速开始（本地运行）

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/social-media-stats.git
cd social-media-stats
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 3. 配置 Facebook（可选）

Facebook 自动获取需要登录后的 Cookie：

1. 用浏览器登录 Facebook
2. 导出 cookies 为 Netscape 格式（可用 [Cookie-Editor](https://cookie-editor.com/) 插件）
3. 保存为 `backend/facebook_cookies.txt`

### 4. 启动服务

Windows：
```bash
start.bat
```

或手动启动：
```bash
cd backend
python app.py
```

### 5. 打开前端

直接双击打开 `index.html`，或访问 http://localhost:5003

## 在线部署

### 架构

- **前端**：Vercel（静态托管）
- **后端**：Render（Docker 部署，支持 Playwright）

### 部署前端到 Vercel

1. Fork 本仓库到 GitHub
2. 登录 [Vercel](https://vercel.com)，导入该仓库
3. 框架预设选择 **Other**（纯静态）
4. 部署完成后获得域名，如 `https://social-stats.vercel.app`

### 部署后端到 Render

1. 登录 [Render](https://render.com)
2. 新建 **Web Service**，选择 Docker 运行时
3. 连接 GitHub 仓库
4. Render 会自动读取根目录的 `Dockerfile` 和 `render.yaml`
5. 部署完成后获得域名，如 `https://social-stats-api.onrender.com`

### 配置前端连接后端

1. 打开部署好的前端页面
2. 点击右上角 **API 设置**
3. 填入 Render 后端地址（如 `https://social-stats-api.onrender.com`）
4. 点击**测试连接**确认正常
5. 点击**保存**

## 环境变量

后端支持以下环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `5003` | 服务监听端口 |

## 文件结构

```
social-media-stats/
├── index.html          # 前端页面（可独立部署）
├── vercel.json         # Vercel 部署配置
├── Dockerfile          # Render Docker 构建
├── render.yaml         # Render 服务配置
├── README.md
├── backend/
│   ├── app.py          # Flask 后端主文件
│   ├── requirements.txt
│   └── facebook_cookies.txt  # Facebook 登录凭证（需自行导出，勿提交到 Git）
```

## 注意事项

- **Facebook**：需要定期更新 `facebook_cookies.txt`，Cookie 过期后需重新导出
- **Instagram**：公开帖子可抓取，频繁请求可能触发 403，建议控制查询频率
- **Threads**：后端使用 Playwright + Chromium，Render 免费版 512MB 内存较紧张，首次查询可能因冷启动较慢
- **小红书**：目前没有任何可靠的免登录自动获取方案，保持手动输入

## License

MIT
