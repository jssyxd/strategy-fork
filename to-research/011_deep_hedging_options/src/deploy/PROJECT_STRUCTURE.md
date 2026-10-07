# 项目文件结构：watch-video-deploy (视频分析与转录 Docker 部署套件)

> **目标项目**：https://github.com/WebDevBar/watch-video  
> **容器技术栈**：Docker, Docker Compose, Python 3.11-slim, Faster-Whisper, Tesseract OCR, FFmpeg, uv

---

## 1. 目录树形结构

```
watch-video-deploy/
├── Dockerfile                   # 多阶段轻量容器镜像定义（集成 ffmpeg + tesseract + uv + whisper）
├── docker-compose.yml           # 双 profile 编排服务配置（交互模式 + 自动化流水线模式）
├── .dockerignore                # 构建排除规则（排除大体积视频与模型缓存）
└── README.md                    # 快速上手与运行命令指南
```

---

## 2. 核心配置文件说明

| 文件名 | 职责 |
|---|---|
| `Dockerfile` | 预装中英双语 Tesseract OCR 及 FFmpeg；内置 uv 环境自动拉取并缓存 Whisper 模型 |
| `docker-compose.yml` | 声明 `watch-video`（交互运行）与 `process`（一次性批处理）两个容器服务 |
| `.dockerignore` | 严禁视频文件、音频中间态、本地 Git 历史注入构建上下文 |
