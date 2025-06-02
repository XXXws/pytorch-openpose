import axios from 'axios'

// 网络状态检测
const isOnline = () => navigator.onLine

// 重试配置
const retryConfig = {
  maxRetries: 3,
  retryDelay: 2000, // 增加重试延迟到2秒
  retryCondition: (error) => {
    return error.isNetworkError || 
           (error.response && error.response.status >= 500) ||
           error.code === 'ECONNABORTED' ||
           error.code === 'NETWORK_ERROR'
  }
}

// API客户端配置
const api = axios.create({
  baseURL: 'http://localhost:8001',
  timeout: 45000, // 增加默认超时到45秒
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    console.log('API请求:', config.method?.toUpperCase(), config.url)
    
    // 检查网络状态
    if (!isOnline()) {
      const error = new Error('网络连接不可用')
      error.code = 'NETWORK_ERROR'
      error.isNetworkError = true
      return Promise.reject(error)
    }
    
    // 添加重试配置到请求配置中
    config.retryCount = config.retryCount || 0
    
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    console.log('API响应:', response.status, response.config.url)
    
    // 验证响应数据格式
    if (response.data && typeof response.data === 'object') {
      // 检查是否有错误标识
      if (response.data.success === false) {
        const error = new Error(response.data.message || '服务器返回错误')
        error.response = response
        return Promise.reject(error)
      }
    }
    
    return response
  },
  error => {
    console.error('响应错误:', error.response?.status, error.message)
    
    // 增强错误信息
    if (error.response) {
      // 服务器响应错误
      error.isServerError = true
      error.statusCode = error.response.status
      error.serverMessage = error.response.data?.detail || error.response.data?.message
    } else if (error.request) {
      // 网络错误
      error.isNetworkError = true
      error.code = 'NETWORK_ERROR'
    } else {
      // 其他错误
      error.isClientError = true
    }
    
    // 重试逻辑
    const config = error.config
    if (config && retryConfig.retryCondition(error)) {
      config.retryCount = config.retryCount || 0
      
      if (config.retryCount < retryConfig.maxRetries) {
        config.retryCount++
        console.log(`重试请求 ${config.retryCount}/${retryConfig.maxRetries}: ${config.url}`)
        
        // 指数退避延迟重试
        const delay = retryConfig.retryDelay * Math.pow(2, config.retryCount - 1)
        return new Promise(resolve => {
          setTimeout(() => {
            resolve(api(config))
          }, delay)
        })
      }
    }
    
    return Promise.reject(error)
  }
)

// API接口封装
export const apiService = {
  // 健康检查
  checkHealth: () => api.get('/api/health', {
    timeout: 25000 // 健康检查25秒超时，给视频处理期间更多时间
  }),
  
  // 设备信息
  getDeviceInfo: () => api.get('/api/device', {
    timeout: 20000 // 设备信息20秒超时
  }),
  
  // 系统信息
  getSystemInfo: () => api.get('/api/system', {
    timeout: 20000 // 系统信息20秒超时
  }),
  
  // 图像检测
  detectImage: (imageData, options = {}) => {
    // 确保Base64数据格式正确
    let base64Data = imageData
    if (base64Data.startsWith('data:image/')) {
      base64Data = base64Data.split(',')[1]
    }
    
    return api.post('/api/detect/image', {
      image_base64: base64Data,
      include_body: options.includeBody !== false,
      include_hands: options.includeHands !== false,
      draw_result: options.drawResult !== false
    }, {
      timeout: 60000 // 图像检测60秒超时
    })
  },
  
  // 视频处理
  uploadVideo: (formData) => {
    return api.post('/api/video/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000 // 视频上传60秒超时
    })
  },
  
  getVideoStatus: (taskId) => api.get(`/api/video/task/${taskId}`, {
    timeout: 30000 // 状态查询30秒超时，给视频处理更多时间
  }),
  
  getVideoResult: (taskId) => api.get(`/api/video/task/${taskId}/result`, {
    timeout: 15000 // 结果获取15秒超时
  }),
  
  // 获取视频结果URL（用于下载）
  getVideoResultUrl: (taskId) => `http://localhost:8001/api/video/task/${taskId}/result`,
  
  // 获取视频播放URL（用于在线播放）
  getVideoPlayUrl: (taskId) => `http://localhost:8001/api/video/task/${taskId}/play`,
  
  // 获取任务详细信息
  getVideoTaskInfo: (taskId) => api.get(`/api/video/task/${taskId}/info`, {
    timeout: 10000 // 任务信息查询10秒超时
  })
}

export default api