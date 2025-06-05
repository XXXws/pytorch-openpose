# PyTorch OpenPose Web System

<div align="center">

![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue.js-4FC08D?style=for-the-badge&logo=vue.js&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)

**一个基于PyTorch的OpenPose人体姿态检测Web应用系统**

*将学术研究项目工程化为用户友好的Web服务*

[🚀 快速开始](#快速开始) • [📖 功能特性](#功能特性) • [🏗️ 系统架构](#系统架构) • [📋 技术文档](System.md)

</div>

## 📖 项目简介

PyTorch OpenPose Web System 是一个现代化的人体姿态检测Web应用，将原始的命令行工具改造为功能完整的Web服务。系统采用前后端分离架构，集成了高性能的AI推理引擎、智能缓存机制和实时通信技术。

### ✨ 核心亮点

- 🎯 **完整Web化改造** - 用户友好的Web界面，支持多种输入方式
- ⚡ **高性能实时处理** - 优化的内存管理和缓冲机制，GPU加速支持
- 🎨 **灵活渲染方案** - 前端Canvas渲染、后端图像渲染、混合模式
- 📊 **完善监控体系** - 实时性能监控、系统健康检查
- 🔧 **技术创新** - 内存池管理、多级帧缓冲、自适应策略

## 🚀 快速开始

### 环境要求

- **Python**: 3.8+ 
- **Node.js**: 16.0+
- **GPU**: NVIDIA GPU (推荐，支持CUDA) 或 CPU
- **内存**: 8GB+ RAM
- **存储**: 2GB+ 可用空间

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/XXXws/pytorch-openpose.git
cd pytorch-openpose
```

2. **安装后端依赖**
```bash
# 推荐使用虚拟环境
pip install -r requirements.txt
```

3. **下载预训练模型**
```bash
# 创建model目录（如果不存在）
mkdir -p model

# 下载body_pose_model.pth到model/目录
# 模型文件约200MB，请确保网络连接稳定
# 下载链接请参考项目文档或联系维护者
```

4. **可选：自定义模型目录**
```bash
# 默认从 `model/` 读取模型，可通过环境变量指定其他目录
export MODEL_DIR=/path/to/your/models
```

5. **安装前端依赖**
```bash
cd frontend
npm install
```

6. **Windows用户快速安装**
```bash
# 运行自动安装脚本
install_dependencies.bat
```

### 启动服务

**后端服务**
```bash
# 开发模式
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**前端服务**
```bash
cd frontend

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 访问应用

- 🌐 **前端界面**: http://localhost:3000
- 🔧 **后端API**: http://localhost:8000
- 📚 **API文档**: http://localhost:8000/docs

## 📸 项目截图

### 🖼️ 图像检测界面
*支持拖拽上传，实时参数调整，结果可视化展示*

### 🎬 视频处理界面
*异步任务管理，进度监控，批量处理支持*

### 📹 实时检测界面
*摄像头实时捕获，多渲染模式，性能监控*

### 📊 系统监控界面
*健康状态检查，设备信息，实时性能指标*

## 🎯 功能特性

### 🖼️ 图像检测
- 支持多种图像格式 (JPEG, PNG, GIF, BMP)
- 拖拽上传，实时参数调整
- 身体19个关键点 + 手部21个关键点检测
- 结果可视化和数据导出

### 🎬 视频处理  
- 支持主流视频格式 (MP4, AVI, MOV)
- 异步后台处理，进度实时监控
- 批量处理和结果下载
- FFmpeg集成，高质量输出

### 📹 实时检测
- 摄像头实时捕获和处理
- WebSocket低延迟通信
- 多种渲染模式可选
- 性能监控和FPS显示

### 📊 系统监控
- 实时性能指标统计
- GPU/CPU使用率监控
- 健康状态检查
- 错误日志和告警

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端展示层     │    │   Web服务层     │    │   AI推理层      │
│                │    │                │    │                │
│  Vue 3 + Vite  │◄──►│  FastAPI       │◄──►│  PyTorch       │
│  Element Plus  │    │  WebSocket     │    │  OpenPose      │
│  Canvas API    │    │  异步处理       │    │  GPU/CPU       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                │
                    ┌─────────────────┐
                    │   性能优化层     │
                    │                │
                    │  内存池管理     │
                    │  帧缓冲队列     │
                    │  自适应策略     │
                    └─────────────────┘
```

## 📋 技术栈

### 后端技术
- **框架**: FastAPI (现代Python Web框架)
- **AI引擎**: PyTorch + OpenPose模型
- **图像处理**: OpenCV
- **视频处理**: FFmpeg
- **实时通信**: WebSocket

### 前端技术  
- **框架**: Vue 3 (Composition API)
- **UI库**: Element Plus
- **构建工具**: Vite
- **HTTP客户端**: Axios
- **图像渲染**: Canvas API

### 性能优化
- **内存管理**: GPU/CPU内存池复用
- **缓冲机制**: 多级帧缓冲队列
- **异步处理**: 6阶段流水线架构
- **智能策略**: 自适应丢帧和压缩

## 📈 性能指标

| 功能模块 | GPU模式 | CPU模式 | 说明 |
|---------|---------|---------|------|
| 实时检测 | 15-25 FPS | 2-5 FPS | 身体+手部检测 |
| 图像处理 | 200-500ms | 1-3s | 单张图像 |
| 内存占用 | 1-2GB | 1-1.5GB | 显存/内存 |
| 网络延迟 | 50-100ms | - | WebSocket通信 |

## 🤝 贡献指南

我们欢迎各种形式的贡献！

1. **Fork** 本仓库
2. **创建** 功能分支 (`git checkout -b feature/AmazingFeature`)
3. **提交** 更改 (`git commit -m 'Add some AmazingFeature'`)
4. **推送** 到分支 (`git push origin feature/AmazingFeature`)
5. **创建** Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [CMU OpenPose](https://github.com/CMU-Perceptual-Computing-Lab/openpose) - 原始OpenPose实现
- [PyTorch](https://pytorch.org/) - 深度学习框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Web框架
- [Vue.js](https://vuejs.org/) - 渐进式前端框架

## 🔧 故障排除

### 常见问题

**Q: GPU不可用怎么办？**
A: 系统会自动切换到CPU模式。检查CUDA安装和驱动程序。

**Q: 模型加载失败？**
A: 确认`body_pose_model.pth`文件存在于`model/`目录中。

**Q: 前端无法连接后端？**
A: 检查后端服务是否在8000端口正常运行。

**Q: 摄像头无法启动？**
A: 检查浏览器摄像头权限设置。

### 性能优化建议

- 🚀 **GPU加速**: 使用NVIDIA GPU可显著提升处理速度
- 💾 **内存优化**: 关闭不必要的应用程序释放内存
- 🌐 **网络优化**: 使用有线网络连接以减少延迟
- 📱 **浏览器选择**: 推荐使用Chrome或Edge浏览器

## 🎓 应用场景

### 🎮 体感游戏开发
- 实时姿态检测实现体感交互
- 支持多人同时检测
- 适用于健身、舞蹈类应用

### 🏃 运动分析系统
- 体育训练动作标准化分析
- 运动员技术动作评估
- 慢动作回放和关键帧标注

### 🛡️ 安防监控智能化
- 人员行为异常检测和预警
- 大规模视频流批量处理
- 集成到现有监控系统

### 🔬 科研教学
- 计算机视觉算法验证
- 人体姿态识别研究
- AI应用开发学习

## 📚 相关文档

- 📋 [系统技术文档](System.md) - 详细的技术架构和实现说明
- 🔧 [API文档](http://localhost:8000/docs) - FastAPI自动生成的接口文档
- 🎨 [前端组件文档](frontend/README.md) - Vue组件使用说明

## 🚀 未来规划

- [ ] 🎯 **3D姿态估计** - 升级到3D关键点检测
- [ ] 👤 **人脸关键点** - 集成人脸检测功能
- [ ] 🤖 **动作识别** - 基于时序分析的行为预测
- [ ] 📱 **移动端适配** - React Native/Flutter应用
- [ ] ☁️ **云端部署** - Kubernetes集群化部署
- [ ] 🔄 **模型优化** - INT8量化和TensorRT加速

## 📞 联系我们

如有问题或建议，请通过以下方式联系：

- 🐛 **问题反馈**: [GitHub Issues](https://github.com/XXXws/pytorch-openpose/issues)
- 💬 **功能建议**: [GitHub Discussions](https://github.com/XXXws/pytorch-openpose/discussions)
- 📖 **技术交流**: 欢迎提交PR和技术讨论

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个Star！⭐**

Made with ❤️ by PyTorch OpenPose Team

</div>
