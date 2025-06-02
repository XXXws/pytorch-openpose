<template>
  <footer class="status-bar">
    <div class="container">
      <div class="status-info">
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="status-item">
              <span class="label">服务状态:</span>
              <el-tag :type="healthStatus.type" size="small">
                {{ healthStatus.text }}
              </el-tag>
            </div>
          </el-col>
          
          <el-col :span="6">
            <div class="status-item">
              <span class="label">计算设备:</span>
              <span class="value">{{ deviceInfo.type }}</span>
            </div>
          </el-col>
          
          <el-col :span="6">
            <div class="status-item">
              <span class="label">内存使用:</span>
              <span class="value">{{ systemInfo.memory }}%</span>
            </div>
          </el-col>
          
          <el-col :span="6">
            <div class="status-item">
              <span class="label">系统时间:</span>
              <span class="value">{{ currentTime }}</span>
            </div>
          </el-col>
        </el-row>
      </div>
    </div>
  </footer>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { apiService } from '../utils/api.js'

export default {
  name: 'StatusBar',
  setup() {
    const currentTime = ref('')
    const healthStatus = reactive({ type: 'info', text: '检查中...' })
    const deviceInfo = reactive({ type: '检测中...' })
    const systemInfo = reactive({ memory: 0 })
    
    let timeInterval = null
    let statusInterval = null
    let checkCount = 0
    let consecutiveErrors = 0
    
    // 更新时间
    const updateTime = () => {
      currentTime.value = new Date().toLocaleTimeString()
    }
    
    // 检查服务状态
    const checkStatus = async () => {
      checkCount++
      
      try {
        // 健康检查
        await apiService.checkHealth()
        healthStatus.type = 'success'
        healthStatus.text = '正常'
        consecutiveErrors = 0 // 重置错误计数
        
        // 只在前几次检查或每5次检查时获取设备和系统信息，减少负载
        if (checkCount <= 3 || checkCount % 5 === 0) {
          try {
            // 设备信息
            const deviceResponse = await apiService.getDeviceInfo()
            deviceInfo.type = deviceResponse.data.device_type
            
            // 系统信息
            const systemResponse = await apiService.getSystemInfo()
            systemInfo.memory = Math.round(systemResponse.data.memory.percent)
          } catch (infoError) {
            // 设备和系统信息获取失败不影响健康状态
            console.warn('获取设备/系统信息失败:', infoError.message)
          }
        }
        
      } catch (error) {
        consecutiveErrors++
        console.warn(`状态检查失败 (${consecutiveErrors}次):`, error.message)
        
        // 根据错误类型设置不同的状态显示
        if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
          // 超时错误 - 可能是服务器忙碌
          healthStatus.type = 'warning'
          healthStatus.text = '处理中'
        } else if (error.isNetworkError || !navigator.onLine) {
          // 网络错误
          healthStatus.type = 'danger'
          healthStatus.text = '网络异常'
        } else if (error.response?.status >= 500) {
          // 服务器错误
          healthStatus.type = 'danger'
          healthStatus.text = '服务异常'
        } else {
          // 其他错误
          healthStatus.type = 'warning'
          healthStatus.text = '检查中'
        }
      }
    }
    
    onMounted(() => {
      updateTime()
      checkStatus()
      
      timeInterval = setInterval(updateTime, 1000)
      // 使用动态间隔进行状态检查
      const scheduleNextCheck = () => {
        // 根据连续错误次数调整检查间隔
        let interval = 60000 // 基础60秒间隔
        if (consecutiveErrors > 0) {
          interval = Math.min(120000, 60000 + consecutiveErrors * 30000) // 有错误时延长间隔，最多2分钟
        }
        
        statusInterval = setTimeout(() => {
          checkStatus().finally(() => {
            scheduleNextCheck() // 检查完成后安排下次检查
          })
        }, interval)
      }
      
      scheduleNextCheck() // 启动动态检查
    })
    
    onUnmounted(() => {
      if (timeInterval) clearInterval(timeInterval)
      if (statusInterval) clearTimeout(statusInterval) // 改为clearTimeout
    })
    
    return {
      currentTime,
      healthStatus,
      deviceInfo,
      systemInfo
    }
  }
}
</script><style scoped>
.status-bar {
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
  padding: 15px 0;
  margin-top: auto;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.value {
  font-size: 14px;
  color: #303133;
  font-weight: 600;
}
</style>