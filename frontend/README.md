# PyTorch OpenPose 前端项目

## 项目简介

这是PyTorch OpenPose Web系统的Vue.js前端项目，专为课程答辩演示设计。

## 功能特性

- 🖼️ **图像检测**: 上传图片进行人体姿态检测
- 🎥 **视频处理**: 上传视频进行批量帧检测
- 📹 **实时检测**: 摄像头实时姿态检测
- 📊 **系统监控**: 实时显示系统状态和性能

## 技术栈

- Vue 3 (Composition API)
- Element Plus (UI组件库)
- Axios (HTTP客户端)
- Vite (构建工具)
- WebSocket (实时通信)

## 快速开始

### 1. 确保后端服务运行

```bash
# 在项目根目录启动后端服务
cd D:\pytorch-openpose-master
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端开发服务器

```bash
# 在frontend目录
cd D:\pytorch-openpose-master\frontend
npm run dev
```

### 3. 访问应用

- 前端地址: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 答辩演示流程

### 第一步: 图像检测演示 (2-3分钟)
1. 切换到"图像检测"标签
2. 上传测试图片
3. 调整检测参数
4. 点击"开始检测"
5. 展示检测结果和关键点数据

### 第二步: 视频处理演示 (2分钟)
1. 切换到"视频处理"标签
2. 上传短视频文件
3. 观察处理进度
4. 播放处理结果

### 第三步: 实时检测演示 (3-4分钟)
1. 切换到"实时检测"标签
2. 启动摄像头
3. 实时展示姿态检测
4. 调整检测参数
5. 展示性能数据

## 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── components/        # Vue组件
│   │   ├── HeaderNav.vue  # 顶部导航
│   │   ├── ImageDemo.vue  # 图像检测
│   │   ├── VideoDemo.vue  # 视频处理
│   │   ├── RealtimeDemo.vue # 实时检测
│   │   └── StatusBar.vue  # 状态栏
│   ├── utils/
│   │   └── api.js         # API客户端
│   ├── styles/
│   │   └── main.css       # 全局样式
│   ├── App.vue            # 主应用组件
│   └── main.js            # 应用入口
├── package.json
└── vite.config.js
```

## 故障排除

### 常见问题

1. **前端无法连接后端**
   - 确保后端服务在8000端口运行
   - 检查防火墙设置

2. **摄像头无法启动**
   - 检查浏览器摄像头权限
   - 确保摄像头未被其他应用占用

3. **WebSocket连接失败**
   - 确保后端WebSocket服务正常
   - 检查网络连接

### 开发模式

```bash
# 开发模式启动
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

## 答辩要点

- 展示前后端分离架构
- 说明Vue 3 Composition API的使用
- 演示WebSocket实时通信
- 展示响应式设计和用户体验
- 说明错误处理和异常恢复机制