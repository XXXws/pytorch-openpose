/**
 * 媒体文件处理工具函数
 * 用于文件验证、格式转换、媒体信息获取等功能
 */

/**
 * 文件大小格式化
 * @param {number} bytes - 字节数
 * @returns {string} 格式化后的文件大小
 */
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 获取文件扩展名
 * @param {string} filename - 文件名
 * @returns {string} 文件扩展名（小写）
 */
export const getFileExtension = (filename) => {
  return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2).toLowerCase()
}

/**
 * 验证图像文件
 * @param {File} file - 文件对象
 * @param {Object} options - 验证选项
 * @returns {Object} 验证结果
 */
export const validateImageFile = (file, options = {}) => {
  const {
    maxSize = 10 * 1024 * 1024, // 默认10MB
    allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp'],
    minWidth = 0,
    minHeight = 0,
    maxWidth = Infinity,
    maxHeight = Infinity
  } = options
  
  const result = {
    valid: true,
    errors: [],
    warnings: []
  }
  
  // 检查文件是否存在
  if (!file) {
    result.valid = false
    result.errors.push('请选择文件')
    return result
  }
  
  // 检查文件类型
  if (!file.type.startsWith('image/')) {
    result.valid = false
    result.errors.push('文件必须是图像格式')
  }
  
  // 检查具体的图像类型
  if (!allowedTypes.includes(file.type)) {
    result.valid = false
    result.errors.push(`支持的格式：${allowedTypes.map(type => type.split('/')[1].toUpperCase()).join(', ')}`)
  }
  
  // 检查文件大小
  if (file.size > maxSize) {
    result.valid = false
    result.errors.push(`文件大小不能超过 ${formatFileSize(maxSize)}`)
  }
  
  // 文件大小警告
  if (file.size > 5 * 1024 * 1024) { // 5MB
    result.warnings.push('文件较大，上传可能需要更长时间')
  }
  
  return result
}

/**
 * 验证视频文件
 * @param {File} file - 文件对象
 * @param {Object} options - 验证选项
 * @returns {Object} 验证结果
 */
export const validateVideoFile = (file, options = {}) => {
  const {
    maxSize = 100 * 1024 * 1024, // 默认100MB
    allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv'],
    maxDuration = 300 // 默认5分钟
  } = options
  
  const result = {
    valid: true,
    errors: [],
    warnings: []
  }
  
  // 检查文件是否存在
  if (!file) {
    result.valid = false
    result.errors.push('请选择文件')
    return result
  }
  
  // 检查文件类型
  if (!file.type.startsWith('video/')) {
    result.valid = false
    result.errors.push('文件必须是视频格式')
  }
  
  // 检查具体的视频类型
  if (!allowedTypes.includes(file.type)) {
    result.valid = false
    result.errors.push(`支持的格式：${allowedTypes.map(type => type.split('/')[1].toUpperCase()).join(', ')}`)
  }
  
  // 检查文件大小
  if (file.size > maxSize) {
    result.valid = false
    result.errors.push(`文件大小不能超过 ${formatFileSize(maxSize)}`)
  }
  
  return result
}

/**
 * 获取图像文件信息
 * @param {File} file - 图像文件
 * @returns {Promise<Object>} 图像信息
 */
export const getImageInfo = (file) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    
    img.onload = () => {
      const info = {
        name: file.name,
        size: file.size,
        type: file.type,
        width: img.naturalWidth,
        height: img.naturalHeight,
        aspectRatio: img.naturalWidth / img.naturalHeight,
        formattedSize: formatFileSize(file.size),
        lastModified: new Date(file.lastModified)
      }
      
      URL.revokeObjectURL(url)
      resolve(info)
    }
    
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('无法读取图像信息'))
    }
    
    img.src = url
  })
}

/**
 * 获取视频文件信息
 * @param {File} file - 视频文件
 * @returns {Promise<Object>} 视频信息
 */
export const getVideoInfo = (file) => {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video')
    const url = URL.createObjectURL(file)
    
    video.onloadedmetadata = () => {
      const info = {
        name: file.name,
        size: file.size,
        type: file.type,
        width: video.videoWidth,
        height: video.videoHeight,
        duration: video.duration,
        aspectRatio: video.videoWidth / video.videoHeight,
        formattedSize: formatFileSize(file.size),
        formattedDuration: formatDuration(video.duration),
        lastModified: new Date(file.lastModified)
      }
      
      URL.revokeObjectURL(url)
      resolve(info)
    }
    
    video.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('无法读取视频信息'))
    }
    
    video.src = url
  })
}

/**
 * 格式化时长
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时长
 */
export const formatDuration = (seconds) => {
  if (isNaN(seconds) || seconds < 0) return '00:00'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  } else {
    return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
}

/**
 * 创建文件预览URL
 * @param {File} file - 文件对象
 * @returns {string} 预览URL
 */
export const createPreviewUrl = (file) => {
  return URL.createObjectURL(file)
}

/**
 * 释放预览URL
 * @param {string} url - 预览URL
 */
export const revokePreviewUrl = (url) => {
  URL.revokeObjectURL(url)
}

/**
 * 检查浏览器支持的文件类型
 * @param {string} type - MIME类型
 * @returns {boolean} 是否支持
 */
export const isSupportedFileType = (type) => {
  const supportedTypes = [
    // 图像格式
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
    // 视频格式
    'video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm'
  ]
  
  return supportedTypes.includes(type)
}

/**
 * 文件拖拽处理工具
 */
export const dragDropHandler = {
  /**
   * 处理拖拽进入事件
   * @param {DragEvent} event - 拖拽事件
   */
  handleDragEnter: (event) => {
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = 'copy'
  },
  
  /**
   * 处理拖拽悬停事件
   * @param {DragEvent} event - 拖拽事件
   */
  handleDragOver: (event) => {
    event.preventDefault()
    event.stopPropagation()
    event.dataTransfer.dropEffect = 'copy'
  },
  
  /**
   * 处理拖拽离开事件
   * @param {DragEvent} event - 拖拽事件
   */
  handleDragLeave: (event) => {
    event.preventDefault()
    event.stopPropagation()
  },
  
  /**
   * 处理文件放置事件
   * @param {DragEvent} event - 拖拽事件
   * @returns {FileList} 文件列表
   */
  handleDrop: (event) => {
    event.preventDefault()
    event.stopPropagation()
    
    const files = event.dataTransfer.files
    return files
  }
}

export default {
  formatFileSize,
  getFileExtension,
  validateImageFile,
  validateVideoFile,
  getImageInfo,
  getVideoInfo,
  formatDuration,
  createPreviewUrl,
  revokePreviewUrl,
  isSupportedFileType,
  dragDropHandler
} 