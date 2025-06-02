<template>
  <div class="realtime-demo">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>实时检测演示</span>
          <div class="header-controls">
            <el-tag v-if="connected" type="success">已连接</el-tag>
            <el-tag v-else type="info">未连接</el-tag>
            <span v-if="fps > 0" class="fps-display">FPS: {{ fps.toFixed(1) }}</span>
          </div>
        </div>
      </template>
      
      <div class="realtime-content">
        <!-- 控制面板 -->
        <div class="controls">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-button 
                v-if="!cameraActive" 
                type="primary" 
                @click="startCamera"
                :loading="starting"
              >
                启动摄像头
              </el-button>
              <el-button 
                v-else 
                type="danger" 
                @click="stopCamera"
              >
                停止检测
              </el-button>
            </el-col>
            
            <el-col :span="8">
              <el-form inline>
                <el-form-item label="身体检测">
                  <el-switch v-model="settings.includeBody" @change="updateSettings" />
                </el-form-item>
                <el-form-item label="手部检测">
                  <el-switch v-model="settings.includeHands" @change="updateSettings" />
                </el-form-item>
              </el-form>
            </el-col>
            
            <el-col :span="8">
              <el-form inline>
                <el-form-item label="渲染模式">
                  <el-select v-model="settings.renderMode" size="small">
                    <el-option label="前端渲染" value="frontend" />
                    <el-option label="后端渲染" value="backend" />
                    <el-option label="混合渲染" value="hybrid" />
                  </el-select>
                </el-form-item>
                <el-form-item label="性能信息">
                  <el-switch v-model="settings.showPerformanceInfo" />
                </el-form-item>
              </el-form>
            </el-col>
            
            <el-col :span="8">
              <div class="stats">
                <p>处理帧数: {{ frameCount }}</p>
                <p>平均处理时间: {{ avgProcessingTime.toFixed(0) }}ms</p>
              </div>
            </el-col>
          </el-row>
        </div>
        
        <!-- 视频显示区域 -->
        <div class="video-area">
          <div class="video-container">
            <video 
              ref="videoRef" 
              autoplay 
              muted 
              playsinline
              class="source-video"
            />
            <canvas 
              ref="canvasRef" 
              class="result-canvas"
            />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template><script>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createRealtimeWebSocket } from '../utils/websocket.js'
import { drawDetectionResults, getDefaultDrawOptions } from '../utils/skeleton.js'

export default {
  name: 'RealtimeDemo',
  setup() {
    const videoRef = ref(null)
    const canvasRef = ref(null)
    const cameraActive = ref(false)
    const starting = ref(false)
    const connected = ref(false)
    const fps = ref(0)
    const frameCount = ref(0)
    const avgProcessingTime = ref(0)
    
    const settings = reactive({
      includeBody: true,
      includeHands: true,
      renderMode: 'frontend', // 'frontend', 'backend', 'hybrid'
      showPerformanceInfo: true
    })
    
    let mediaStream = null
    let websocketManager = null
    let animationFrame = null
    let processingTimes = []
    let lastFrameTime = 0
    let fpsCounter = 0
    
    // 骨架绘制选项
    const drawOptions = reactive(getDefaultDrawOptions())
    
    // 性能监控
    const performanceStats = reactive({
      renderTime: 0,
      networkLatency: 0,
      detectionTime: 0,
      frameDrops: 0
    })
    
    // 绘制性能信息
    const drawPerformanceInfo = (ctx, data) => {
      if (!settings.showPerformanceInfo) return
      
      ctx.save()
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(10, 10, 200, 120)
      
      ctx.fillStyle = '#00ff00'
      ctx.font = '12px monospace'
      
      const info = [
        `FPS: ${fps.value.toFixed(1)}`,
        `处理时间: ${(data.processing_time * 1000).toFixed(0)}ms`,
        `网络延迟: ${performanceStats.networkLatency.toFixed(0)}ms`,
        `渲染模式: ${settings.renderMode}`,
        `检测到: ${data.keypoints_summary?.total_people || 0}人`,
        `手部: ${data.keypoints_summary?.total_hands || 0}个`,
        `帧数: ${frameCount.value}`
      ]
      
      info.forEach((text, index) => {
        ctx.fillText(text, 15, 30 + index * 15)
      })
      
      ctx.restore()
    }
    
    const startCamera = async () => {
      starting.value = true
      
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 }
        })
        
        videoRef.value.srcObject = mediaStream
        cameraActive.value = true
        
        // 连接WebSocket
        connectWebSocket()
        
        ElMessage.success('摄像头启动成功')
      } catch (error) {
        ElMessage.error('摄像头启动失败: ' + error.message)
      } finally {
        starting.value = false
      }
    }
    
    const stopCamera = () => {
      if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop())
        mediaStream = null
      }
      
      if (websocketManager) {
        websocketManager.destroy()
        websocketManager = null
      }
      
      if (animationFrame) {
        cancelAnimationFrame(animationFrame)
      }
      
      cameraActive.value = false
      connected.value = false
      fps.value = 0
      frameCount.value = 0
    }    
    const connectWebSocket = () => {
      const clientId = 'demo_client_' + Date.now()
      
      websocketManager = createRealtimeWebSocket(clientId, {
        includeBody: settings.includeBody,
        includeHands: settings.includeHands,
        targetFps: 10,
        onOpen: () => {
          connected.value = true
          ElMessage.success('实时检测连接成功')
          startFrameCapture()
        },
        onMessage: (data) => {
          if (data.type === 'detection_result') {
            handleDetectionResult(data)
          }
        },
        onClose: (event) => {
          connected.value = false
          if (!event.wasClean) {
            ElMessage.warning('WebSocket连接断开')
          }
        },
        onError: (error) => {
          console.error('WebSocket错误:', error)
          ElMessage.error('WebSocket连接错误')
          connected.value = false
        },
        onReconnect: (attempt) => {
          ElMessage.info(`正在尝试重连... (${attempt}/5)`)
        }
      })
      
      websocketManager.connect()
    }
    
    const startFrameCapture = () => {
      let captureCanvas = null
      let captureCtx = null
      let lastFpsTime = Date.now()
      
      const captureFrame = (timestamp) => {
        if (!cameraActive.value || !connected.value) return
        
        // FPS控制 - 限制为15fps，提升响应性
        if (timestamp - lastFrameTime < 67) { // 67ms ≈ 15fps
          animationFrame = requestAnimationFrame(captureFrame)
          return
        }
        
        lastFrameTime = timestamp
        
        const video = videoRef.value
        
        if (video && video.videoWidth > 0 && video.readyState >= 2) {
          // 创建专用的捕获canvas，避免与显示canvas冲突
          if (!captureCanvas || captureCanvas.width !== video.videoWidth || captureCanvas.height !== video.videoHeight) {
            captureCanvas = document.createElement('canvas')
            captureCanvas.width = video.videoWidth
            captureCanvas.height = video.videoHeight
            captureCtx = captureCanvas.getContext('2d')
            console.log(`创建捕获Canvas: ${captureCanvas.width}x${captureCanvas.height}`)
          }
          
          // 绘制当前视频帧到捕获canvas
          captureCtx.drawImage(video, 0, 0)
          
          // 转换为base64并发送
          const imageData = captureCanvas.toDataURL('image/jpeg', 0.7) // 降低质量提升性能
          
          if (websocketManager && websocketManager.isConnected()) {
            websocketManager.send({
              type: 'frame',
              image: imageData.split(',')[1], // 只发送base64数据部分
              timestamp: Date.now(),
              frame_id: frameCount.value
            })
            
            frameCount.value++
            
            // 优化FPS计算
            fpsCounter++
            const now = Date.now()
            if (now - lastFpsTime >= 1000) { // 每秒计算一次FPS
              fps.value = fpsCounter * 1000 / (now - lastFpsTime)
              fpsCounter = 0
              lastFpsTime = now
            }
          }
        }
        
        animationFrame = requestAnimationFrame(captureFrame)
      }
      
      animationFrame = requestAnimationFrame(captureFrame)
    }    
    const handleDetectionResult = (data) => {
      // 更新处理时间统计
      if (data.processing_time) {
        processingTimes.push(data.processing_time * 1000) // 转换为毫秒
        if (processingTimes.length > 30) {
          processingTimes.shift()
        }
        avgProcessingTime.value = processingTimes.reduce((a, b) => a + b, 0) / processingTimes.length
      }
      
      const canvas = canvasRef.value
      const video = videoRef.value
      
      if (!canvas || !video) return
      
      const ctx = canvas.getContext('2d')
      
      // 只在必要时调整canvas尺寸，避免频繁重设
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        console.log(`Canvas尺寸调整为: ${canvas.width}x${canvas.height}`)
      }
      
      // 混合渲染机制
      if (settings.renderMode === 'frontend' && data.detection_results) {
        // 前端渲染模式：使用关键点数据
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        
        // 绘制检测结果
        drawDetectionResults(ctx, data.detection_results, {
          drawBody: settings.includeBody,
          drawHands: settings.includeHands,
          ...drawOptions
        })
        
        // 显示性能信息
        if (settings.showPerformanceInfo) {
          drawPerformanceInfo(ctx, data)
        }
        
      } else if (settings.renderMode === 'backend' && data.result_image) {
        // 后端渲染模式：使用后端绘制的图像
        const img = new Image()
        img.onload = () => {
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        }
        
        let imageData = data.result_image
        if (!imageData.startsWith('data:image/')) {
          imageData = 'data:image/jpeg;base64,' + imageData
        }
        img.src = imageData
        
      } else if (settings.renderMode === 'hybrid') {
        // 混合渲染模式：前端优先，后端备用
        if (data.detection_results) {
          // 使用前端渲染
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          drawDetectionResults(ctx, data.detection_results, {
            drawBody: settings.includeBody,
            drawHands: settings.includeHands,
            ...drawOptions
          })
        } else if (data.result_image) {
          // 降级到后端渲染
          const img = new Image()
          img.onload = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
          }
          
          let imageData = data.result_image
          if (!imageData.startsWith('data:image/')) {
            imageData = 'data:image/jpeg;base64,' + imageData
          }
          img.src = imageData
        }
      }
    }
    

    
    const updateSettings = () => {
      if (websocketManager && websocketManager.isConnected()) {
        websocketManager.send({
          type: 'settings',
          include_body: settings.includeBody,
          include_hands: settings.includeHands
        })
        
        ElMessage.info('检测参数已更新')
      }
    }
    
    onUnmounted(() => {
      stopCamera()
    })
    
    return {
      videoRef,
      canvasRef,
      cameraActive,
      starting,
      connected,
      fps,
      frameCount,
      avgProcessingTime,
      settings,
      startCamera,
      stopCamera,
      updateSettings
    }
  }
}
</script><style scoped>
.realtime-demo {
  padding: 20px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.fps-display {
  font-weight: bold;
  color: #409eff;
}

.controls {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stats p {
  margin: 5px 0;
  font-size: 14px;
  color: #606266;
}

.video-area {
  display: flex;
  justify-content: center;
}

.video-container {
  position: relative;
  width: 640px;
  height: 480px;
}

.source-video {
  position: absolute;
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
  opacity: 0.3;
}

.result-canvas {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 4px;
  border: 2px solid #409eff;
}
</style>