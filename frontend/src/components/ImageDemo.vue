<template>
  <div class="image-demo">
    <el-row :gutter="20">
      <!-- 左侧控制区 -->
      <el-col :span="8">
        <el-card class="control-panel">
          <template #header>
            <div class="card-header">
              <span>图像检测控制</span>
            </div>
          </template>
          
          <!-- 文件上传 -->
          <div class="upload-section">
            <el-upload
              ref="uploadRef"
              class="image-uploader"
              drag
              :show-file-list="false"
              :before-upload="beforeUpload"
              accept="image/*"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                拖拽图片到这里，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 jpg/png 格式，文件大小不超过10MB
                </div>
              </template>
            </el-upload>
          </div>
          
          <!-- 参数设置 -->
          <div class="params-section">
            <h4>检测参数</h4>
            <el-form label-width="80px">
              <el-form-item label="身体检测">
                <el-switch v-model="params.includeBody" />
              </el-form-item>
              <el-form-item label="手部检测">
                <el-switch v-model="params.includeHands" />
              </el-form-item>
              <el-form-item label="绘制结果">
                <el-switch v-model="params.drawResult" />
              </el-form-item>
            </el-form>
          </div>
          
          <!-- 处理按钮 -->
          <div class="action-section">
            <el-button 
              type="primary" 
              size="large"
              :loading="processing"
              :disabled="!currentImage"
              @click="detectImage"
              block
            >
              {{ processing ? '检测中...' : '开始检测' }}
            </el-button>
          </div>
        </el-card>
      </el-col>      
      <!-- 右侧结果展示区 -->
      <el-col :span="16">
        <el-card class="result-panel">
          <template #header>
            <div class="card-header">
              <span>检测结果</span>
              <el-tag v-if="lastResult" type="success">
                检测完成 - {{ lastResult.processing_time }}ms
              </el-tag>
            </div>
          </template>
          
          <div class="result-content">
            <!-- 图像对比显示 -->
            <div v-if="currentImage || resultImage" class="image-comparison">
              <div class="image-item">
                <h4>原始图像</h4>
                <img v-if="currentImage" :src="currentImage" alt="原始图像" />
                <div v-else class="placeholder">请上传图像</div>
              </div>
              
              <div class="image-item">
                <h4>检测结果</h4>
                <img v-if="resultImage" :src="resultImage" alt="检测结果" />
                <div v-else class="placeholder">等待检测</div>
              </div>
            </div>
            
            <!-- 检测统计 -->
            <div v-if="lastResult" class="detection-stats">
              <el-descriptions title="检测统计" :column="2" border>
                <el-descriptions-item label="检测人数">
                  <el-tag type="success" size="large">
                    {{ lastResult.detection_results?.body?.num_people || 0 }} 人
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="检测手数">
                  <el-tag type="warning" size="large">
                    {{ lastResult.detection_results?.hands?.num_hands || 0 }} 只
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="处理时间">
                  <el-tag type="info" size="large">
                    {{ Math.round(lastResult.processing_time) }}ms
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="使用设备">
                  <el-tag :type="lastResult.device.includes('cuda') ? 'success' : 'info'" size="large">
                    {{ lastResult.device.includes('cuda') ? 'GPU加速' : 'CPU处理' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="检测时间">
                  {{ new Date(lastResult.timestamp).toLocaleString() }}
                </el-descriptions-item>
                <el-descriptions-item label="图像尺寸" v-if="lastResult.detection_results?.image_size">
                  {{ lastResult.detection_results.image_size.width }} × {{ lastResult.detection_results.image_size.height }}
                </el-descriptions-item>
              </el-descriptions>
              
              <!-- 关键点详细信息 -->
              <div v-if="lastResult.detection_results?.body || lastResult.detection_results?.hands" class="keypoints-info">
                <h4>关键点详细信息</h4>
                <el-row :gutter="10">
                  <el-col :span="12">
                    <el-card shadow="never" class="info-card">
                      <template #header>身体关键点</template>
                      <div class="keypoint-item">
                        <span>检测人数：</span>
                        <el-tag size="small">{{ lastResult.detection_results.body?.num_people || 0 }}</el-tag>
                      </div>
                      <div class="keypoint-item">
                        <span>关键点总数：</span>
                        <el-tag size="small">{{ lastResult.detection_results.body?.num_keypoints || 0 }}</el-tag>
                      </div>
                      <div class="keypoint-item">
                        <span>处理时间：</span>
                        <el-tag size="small">{{ lastResult.detection_results.body?.processing_time || 0 }}s</el-tag>
                      </div>
                    </el-card>
                  </el-col>
                  <el-col :span="12">
                    <el-card shadow="never" class="info-card">
                      <template #header>手部关键点</template>
                      <div class="keypoint-item">
                        <span>检测手数：</span>
                        <el-tag size="small">{{ lastResult.detection_results.hands?.num_hands || 0 }}</el-tag>
                      </div>
                      <div class="keypoint-item">
                        <span>处理时间：</span>
                        <el-tag size="small">{{ lastResult.detection_results.hands?.processing_time || 0 }}s</el-tag>
                      </div>
                      <div class="keypoint-item">
                        <span>手部数据：</span>
                        <el-tag size="small">{{ lastResult.detection_results.hands?.hands_data?.length || 0 }} 组</el-tag>
                      </div>
                    </el-card>
                  </el-col>
                </el-row>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template><script>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { apiService } from '../utils/api.js'
import { validateImageFile } from '../utils/media.js'
import { fileToBase64 } from '../utils/canvas.js'

export default {
  name: 'ImageDemo',
  components: {
    UploadFilled
  },
  setup() {
    const processing = ref(false)
    const currentImage = ref('')
    const resultImage = ref('')
    const lastResult = ref(null)
    
    const params = reactive({
      includeBody: true,
      includeHands: true,
      drawResult: true
    })
    
    // 文件上传前处理
    const beforeUpload = async (file) => {
      // 使用工具函数验证文件
      const validation = validateImageFile(file)
      
      if (!validation.valid) {
        validation.errors.forEach(error => {
          ElMessage.error(error)
        })
        return false
      }
      
      // 显示警告信息
      validation.warnings.forEach(warning => {
        ElMessage.warning(warning)
      })
      
      try {
        // 使用工具函数转换为Base64
        const base64 = await fileToBase64(file)
        currentImage.value = base64
        resultImage.value = '' // 清空之前的结果
        lastResult.value = null
        
        ElMessage.success('图像上传成功，可以开始检测')
      } catch (error) {
        console.error('文件处理错误:', error)
        ElMessage.error('文件处理失败: ' + error.message)
      }
      
      return false // 阻止自动上传
    }    
    // 执行图像检测
    const detectImage = async () => {
      if (!currentImage.value) {
        ElMessage.warning('请先上传图像')
        return
      }
      
      processing.value = true
      
      try {
        ElMessage.info('正在进行姿态检测，请稍候...')
        
        const response = await apiService.detectImage(
          currentImage.value,
          {
            includeBody: params.includeBody,
            includeHands: params.includeHands,
            drawResult: params.drawResult
          }
        )
        
        if (response.data.success) {
          lastResult.value = response.data
          
          // 调试日志：输出完整的检测结果结构
          console.log('检测结果详细信息:', JSON.stringify(response.data.detection_results, null, 2))
          
          // 处理结果图像
          if (response.data.result_image) {
            // 确保Base64图像有正确的前缀
            let resultImageData = response.data.result_image
            if (!resultImageData.startsWith('data:image/')) {
              resultImageData = 'data:image/jpeg;base64,' + resultImageData
            }
            resultImage.value = resultImageData
          }
          
          // 显示检测统计信息 - 增强数据验证
          const stats = response.data.detection_results
          
          // 验证数据结构并提供降级方案
          let bodyCount = 0
          let handCount = 0
          
          if (stats?.body && typeof stats.body === 'object') {
            bodyCount = stats.body.num_people || 0
            console.log('身体检测结果:', stats.body)
          }
          
          if (stats?.hands && typeof stats.hands === 'object') {
            handCount = stats.hands.num_hands || 0
            console.log('手部检测结果:', stats.hands)
          }
          
          // 如果没有检测到预期的数据结构，尝试兼容旧格式
          if (bodyCount === 0 && handCount === 0) {
            bodyCount = stats?.body_count || 0
            handCount = stats?.hand_count || 0
            console.warn('使用兼容模式读取检测结果')
          }
          
          ElMessage.success(
            `检测完成！检测到 ${bodyCount} 个人体，${handCount} 只手部，耗时 ${Math.round(response.data.processing_time)}ms`
          )
        } else {
          ElMessage.error('检测失败: ' + (response.data.message || '未知错误'))
        }
      } catch (error) {
        console.error('检测错误:', error)
        
        // 更详细的错误处理
        let errorMessage = '检测失败'
        if (error.response) {
          // 服务器响应错误
          errorMessage = `服务器错误 (${error.response.status}): ${error.response.data?.detail || error.message}`
        } else if (error.request) {
          // 网络错误
          errorMessage = '网络连接失败，请检查后端服务是否启动'
        } else {
          // 其他错误
          errorMessage = error.message
        }
        
        ElMessage.error(errorMessage)
      } finally {
        processing.value = false
      }
    }
    
    return {
      processing,
      currentImage,
      resultImage,
      lastResult,
      params,
      beforeUpload,
      detectImage
    }
  }
}
</script><style scoped>
/* 引入主样式文件中的样式，这里只添加组件特有的样式 */

/* 加载状态覆盖层 */
.image-item {
  position: relative;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  z-index: 1000;
}

.loading-text {
  margin-top: 10px;
  color: #409eff;
  font-size: 14px;
  font-weight: 500;
}

/* 结果动画 */
.result-fade-enter-active {
  transition: all 0.5s ease;
}

.result-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.result-fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}

/* 上传区域拖拽状态 */
.upload-dragover {
  border-color: #409eff !important;
  background-color: #f0f9ff !important;
}

.upload-dragover .el-icon--upload {
  color: #409eff !important;
  transform: scale(1.1);
}

/* 检测按钮加载状态 */
.detecting-button {
  background: linear-gradient(135deg, #409eff 0%, #667eea 100%) !important;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(64, 158, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0); }
}

/* 统计卡片动画 */
.stats-card {
  animation: slideInUp 0.6s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 图像对比容器 */
.image-comparison {
  position: relative;
}

/* 成功状态指示 */
.success-indicator {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #67c23a;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  z-index: 10;
}

/* 处理进度指示 */
.progress-indicator {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 12px;
  z-index: 10;
}
</style>