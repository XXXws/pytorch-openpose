<template>
  <div class="video-demo">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>视频处理演示</span>
          <el-tag v-if="currentTask" :type="getStatusType(currentTask.status)">
            {{ getStatusText(currentTask.status) }}
          </el-tag>
        </div>
      </template>
      
      <div class="video-content">
        <!-- 视频上传区域 -->
        <div v-if="!currentTask" class="upload-area">
          <el-upload
            class="video-uploader"
            drag
            :show-file-list="false"
            :before-upload="beforeUpload"
            accept="video/*"
          >
            <el-icon class="el-icon--upload"><VideoPlay /></el-icon>
            <div class="el-upload__text">
              拖拽视频到这里，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 mp4/avi/mov 格式，建议30秒内短视频
              </div>
            </template>
          </el-upload>
        </div>
        
        <!-- 处理进度显示 -->
        <div v-if="currentTask && currentTask.status === 'processing'" class="progress-area">
          <h3>视频处理中...</h3>
          <el-progress 
            :percentage="currentTask.progress || 0" 
            :status="currentTask.progress === 100 ? 'success' : ''"
          />
          <p>{{ currentTask.message || '正在处理视频帧...' }}</p>
        </div>
        
        <!-- 结果显示 -->
        <div v-if="currentTask && currentTask.status === 'completed'" class="result-area">
          <h3>处理完成</h3>
          <video 
            v-if="currentTask.result_url" 
            :src="currentTask.result_url" 
            controls 
            class="result-video"
            @error="handleVideoError"
            @loadstart="handleVideoLoadStart"
            @canplay="handleVideoCanPlay"
          />
          
          <el-descriptions title="处理统计" :column="2" border>
            <el-descriptions-item label="总帧数">
              {{ currentTask.total_frames || 0 }}
            </el-descriptions-item>
            <el-descriptions-item label="处理时间">
              {{ currentTask.processing_time || 0 }}s
            </el-descriptions-item>
          </el-descriptions>
          
          <div class="actions">
            <el-button @click="resetTask">处理新视频</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template><script>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { apiService } from '../utils/api.js'
import { validateVideoFile, formatFileSize } from '../utils/media.js'

export default {
  name: 'VideoDemo',
  components: {
    VideoPlay
  },
  setup() {
    const currentTask = ref(null)
    const polling = ref(null)
    
    const beforeUpload = async (file) => {
      // 使用工具函数验证视频文件
      const validation = validateVideoFile(file, {
        maxSize: 100 * 1024 * 1024, // 100MB
        allowedTypes: ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/webm']
      })
      
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
      
      // 上传视频
      const formData = new FormData()
      formData.append('file', file)
      
      try {
        ElMessage.info('开始上传视频...')
        const response = await apiService.uploadVideo(formData)
        
        if (response.data.success) {
          currentTask.value = {
            task_id: response.data.task_id,
            status: 'processing',
            progress: 0,
            file_name: file.name,
            file_size: formatFileSize(file.size),
            start_time: new Date().toLocaleString()
          }
          
          startPolling()
          ElMessage.success('视频上传成功，开始处理...')
        } else {
          ElMessage.error('视频上传失败: ' + (response.data.message || '未知错误'))
        }
      } catch (error) {
        console.error('视频上传错误:', error)
        
        let errorMessage = '视频上传失败'
        if (error.response) {
          errorMessage = `服务器错误 (${error.response.status}): ${error.response.data?.detail || error.message}`
        } else if (error.request) {
          errorMessage = '网络连接失败，请检查后端服务是否启动'
        } else {
          errorMessage = error.message
        }
        
        ElMessage.error(errorMessage)
      }
      
      return false
    }    
    const startPolling = () => {
      let pollCount = 0
      let consecutiveErrors = 0
      const maxPollCount = 300 // 最多轮询10分钟
      const maxConsecutiveErrors = 10 // 最多连续10次错误
      
      const pollTask = async () => {
        pollCount++
        
        // 检查网络状态
        if (!navigator.onLine) {
          console.warn('网络连接断开，暂停轮询')
          currentTask.value.network_status = 'offline'
          // 网络断开时延迟重试
          polling.value = setTimeout(pollTask, 5000)
          return
        } else {
          currentTask.value.network_status = 'online'
        }
        
        try {
          const response = await apiService.getVideoStatus(currentTask.value.task_id)
          const status = response.data
          
          // 重置错误计数
          consecutiveErrors = 0
          
          // 更新任务状态
          currentTask.value = { 
            ...currentTask.value, 
            ...status,
            poll_count: pollCount,
            consecutive_errors: consecutiveErrors,
            last_update: new Date().toLocaleString(),
            network_status: 'online'
          }
          
          if (status.status === 'completed') {
            // 设置结果视频URL，使用播放专用的API端点
            currentTask.value.result_url = apiService.getVideoPlayUrl(currentTask.value.task_id)
            currentTask.value.end_time = new Date().toLocaleString()
            
            ElMessage.success(`视频处理完成！共处理 ${status.total_frames || 0} 帧，耗时 ${status.processing_time || 0} 秒`)
            return // 完成时停止轮询
          } else if (status.status === 'failed') {
            currentTask.value.end_time = new Date().toLocaleString()
            ElMessage.error(`视频处理失败: ${status.error_message || '未知错误'}`)
            return // 失败时停止轮询
          } else if (pollCount >= maxPollCount) {
            currentTask.value.status = 'timeout'
            currentTask.value.end_time = new Date().toLocaleString()
            ElMessage.error('视频处理超时，请重试或联系管理员')
            return // 超时时停止轮询
          }
        } catch (error) {
          consecutiveErrors++
          console.error(`轮询错误 (${consecutiveErrors}/${maxConsecutiveErrors}):`, error)
          
          // 更新错误状态
          currentTask.value.consecutive_errors = consecutiveErrors
          currentTask.value.last_error = error.message
          
          // 根据错误类型提供不同的处理
          if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
            // 超时错误 - 可能是服务器忙碌，减少警告频率
            if (consecutiveErrors === 1) {
              console.log('状态查询超时，服务器可能正在处理，继续轮询...')
            } else if (consecutiveErrors === 5) {
              ElMessage.warning('服务器响应较慢，请耐心等待...')
            }
          } else if (error.response?.status >= 500) {
            // 服务器错误
            if (consecutiveErrors === 3) {
              ElMessage.warning('服务器暂时不可用，正在重试...')
            }
          } else if (!navigator.onLine) {
            // 网络断开
            ElMessage.warning('网络连接断开，请检查网络状态')
            currentTask.value.network_status = 'offline'
          } else {
            // 其他错误
            if (consecutiveErrors % 5 === 0) {
              ElMessage.warning(`获取处理状态失败 (${consecutiveErrors}次)，正在重试...`)
            }
          }
          
          // 连续错误过多时停止轮询
          if (consecutiveErrors >= maxConsecutiveErrors) {
            currentTask.value.status = 'error'
            currentTask.value.end_time = new Date().toLocaleString()
            ElMessage.error('连续获取状态失败，请检查网络连接或重新开始处理')
            return // 错误过多时停止轮询
          }
        }
        
        // 继续下一次轮询，使用动态间隔
        const nextInterval = getPollingInterval(pollCount, consecutiveErrors)
        polling.value = setTimeout(pollTask, nextInterval)
      }
      
      // 启动第一次轮询
      pollTask()
    }
    
    // 根据轮询次数和错误情况动态调整间隔
    const getPollingInterval = (pollCount, consecutiveErrors = 0) => {
      // 基础间隔策略
      let baseInterval
      if (pollCount < 20) baseInterval = 3000      // 前1分钟：3秒间隔
      else if (pollCount < 60) baseInterval = 5000 // 1-3分钟：5秒间隔  
      else if (pollCount < 120) baseInterval = 8000 // 3-6分钟：8秒间隔
      else baseInterval = 15000                     // 6分钟后：15秒间隔
      
      // 如果有连续错误，增加间隔以减少服务器压力
      if (consecutiveErrors > 0) {
        baseInterval = baseInterval * Math.min(2, 1 + consecutiveErrors * 0.5)
      }
      
      return Math.min(baseInterval, 30000) // 最大间隔30秒
    }
    
    const resetTask = () => {
      currentTask.value = null
      if (polling.value) {
        clearTimeout(polling.value) // 改为clearTimeout，因为现在使用setTimeout
      }
    }
    
    const getStatusType = (status) => {
      const types = {
        processing: 'warning',
        completed: 'success',
        failed: 'danger'
      }
      return types[status] || 'info'
    }
    
    const getStatusText = (status) => {
      const texts = {
        processing: '处理中',
        completed: '已完成',
        failed: '处理失败'
      }
      return texts[status] || status
    }
    
    // 视频播放事件处理
    const handleVideoError = async (event) => {
      console.error('视频播放错误:', event)
      
      // 获取更详细的错误信息
      const video = event.target
      let errorMessage = '视频播放失败'
      
      // 添加详细的调试信息
      console.log('视频源URL:', video.src)
      console.log('视频当前状态:', {
        readyState: video.readyState,
        networkState: video.networkState,
        currentTime: video.currentTime,
        duration: video.duration
      })
      
      if (video.error) {
        console.log('视频错误详情:', {
          code: video.error.code,
          message: video.error.message
        })
        
        switch (video.error.code) {
          case video.error.MEDIA_ERR_ABORTED:
            errorMessage = '视频播放被中止'
            break
          case video.error.MEDIA_ERR_NETWORK:
            errorMessage = '网络错误导致视频下载失败'
            break
          case video.error.MEDIA_ERR_DECODE:
            errorMessage = '视频解码失败，文件可能损坏'
            break
          case video.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
            errorMessage = '视频格式不支持或文件损坏'
            break
          default:
            errorMessage = `视频播放错误 (代码: ${video.error.code})`
        }
      }
      
      // 尝试验证视频URL是否可访问
      let urlAccessible = false
      try {
        console.log('检查视频URL可访问性:', video.src)
        const response = await fetch(video.src, { method: 'HEAD' })
        console.log('HEAD请求响应:', {
          status: response.status,
          statusText: response.statusText,
          headers: Object.fromEntries(response.headers.entries())
        })
        
        if (response.ok) {
          urlAccessible = true
          console.log('视频URL可访问，但播放仍然失败')
        } else {
          errorMessage += ` - 服务器响应: ${response.status} ${response.statusText}`
          console.log('HEAD请求失败:', response.status, response.statusText)
        }
      } catch (fetchError) {
        console.log('HEAD请求异常:', fetchError)
        errorMessage += ` - 网络连接失败: ${fetchError.message}`
      }
      
      // 如果原始URL不可访问，尝试备用访问方式
      if (!urlAccessible && currentTask.value && currentTask.value.task_id) {
        console.log('尝试备用视频访问方式...')
        
        try {
          // 尝试通过任务列表获取可用的视频文件
          const tasksResponse = await apiService.getVideoTaskInfo(currentTask.value.task_id)
          if (tasksResponse.data && tasksResponse.data.task_info && tasksResponse.data.task_info.output_file) {
            // 从输出文件路径提取文件名
            const outputFile = tasksResponse.data.task_info.output_file
            const filename = outputFile.split('/').pop() || outputFile.split('\\').pop()
            
            if (filename && filename.endsWith('.mp4')) {
              // 使用直接文件访问端点
              const backupUrl = `http://localhost:8000/api/video/file/${filename}`
              
              // 验证备用URL是否可访问
              console.log('尝试备用URL:', backupUrl)
              const backupResponse = await fetch(backupUrl, { method: 'HEAD' })
              console.log('备用URL响应:', {
                status: backupResponse.status,
                statusText: backupResponse.statusText,
                headers: Object.fromEntries(backupResponse.headers.entries())
              })
              
              if (backupResponse.ok) {
                console.log('备用URL可用，切换视频源...')
                currentTask.value.result_url = backupUrl
                video.src = backupUrl
                video.load() // 重新加载视频
                ElMessage.success('已切换到备用视频源，正在重新加载...')
                return // 不显示错误消息，让视频重新加载
              } else {
                console.log('备用URL也不可访问:', backupResponse.status)
              }
            }
          }
        } catch (backupError) {
          console.error('备用访问方式失败:', backupError)
        }
        
        // 如果备用方式也失败，尝试扫描可用的视频文件
        try {
          console.log('尝试扫描可用视频文件...')
          const tasksResponse = await fetch('http://localhost:8000/api/video/tasks')
          if (tasksResponse.ok) {
            const tasksData = await tasksResponse.json()
            
            // 查找最近完成的任务
            const completedTasks = tasksData.tasks.filter(task => task.status === 'completed')
            if (completedTasks.length > 0) {
              // 使用最新的完成任务
              const latestTask = completedTasks.sort((a, b) => (b.end_time || 0) - (a.end_time || 0))[0]
              if (latestTask.output_file) {
                const filename = latestTask.output_file.split('/').pop() || latestTask.output_file.split('\\').pop()
                if (filename && filename.endsWith('.mp4')) {
                  const scanUrl = `http://localhost:8000/api/video/file/${filename}`
                  const scanResponse = await fetch(scanUrl, { method: 'HEAD' })
                  if (scanResponse.ok) {
                    console.log('找到可用视频文件，切换视频源...')
                    currentTask.value.result_url = scanUrl
                    video.src = scanUrl
                    video.load()
                    ElMessage.success('已找到可用视频文件，正在重新加载...')
                    return
                  }
                }
              }
            }
          }
        } catch (scanError) {
          console.error('扫描视频文件失败:', scanError)
        }
      }
      
      ElMessage.error(errorMessage)
      
      // 提供重试选项
      ElMessage({
        message: '视频播放失败，是否重新处理视频？',
        type: 'warning',
        showClose: true,
        duration: 10000,
        dangerouslyUseHTMLString: true,
        customClass: 'video-error-message'
      })
    }
    
    const handleVideoLoadStart = () => {
      console.log('开始加载视频...')
    }
    
    const handleVideoCanPlay = () => {
      console.log('视频可以播放')
      ElMessage.success('视频加载成功，可以播放')
    }
    
    return {
      currentTask,
      beforeUpload,
      resetTask,
      getStatusType,
      getStatusText,
      startPolling,
      getPollingInterval,
      handleVideoError,
      handleVideoLoadStart,
      handleVideoCanPlay
    }
  }
}
</script><style scoped>
.video-demo {
  padding: 20px 0;
}

.video-content {
  min-height: 400px;
}

.upload-area {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}

.video-uploader {
  width: 100%;
  max-width: 400px;
}

.progress-area {
  text-align: center;
  padding: 40px;
}

.progress-area h3 {
  margin-bottom: 20px;
}

.result-area {
  text-align: center;
}

.result-video {
  width: 100%;
  max-width: 600px;
  margin: 20px 0;
}

.actions {
  margin-top: 20px;
}
</style>
