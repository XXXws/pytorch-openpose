/**
 * Canvas和图像处理工具函数
 * 用于Vue前端的图像处理、Base64转换等功能
 */

/**
 * 将文件转换为Base64编码
 * @param {File} file - 文件对象
 * @returns {Promise<string>} Base64编码字符串
 */
export const fileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * 将Base64字符串转换为Blob对象
 * @param {string} base64 - Base64编码字符串
 * @param {string} mimeType - MIME类型，默认为image/jpeg
 * @returns {Blob} Blob对象
 */
export const base64ToBlob = (base64, mimeType = 'image/jpeg') => {
  const byteCharacters = atob(base64.split(',')[1] || base64)
  const byteNumbers = new Array(byteCharacters.length)
  
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i)
  }
  
  const byteArray = new Uint8Array(byteNumbers)
  return new Blob([byteArray], { type: mimeType })
}

/**
 * 调整图像尺寸
 * @param {string} imageSrc - 图像源（Base64或URL）
 * @param {number} maxWidth - 最大宽度
 * @param {number} maxHeight - 最大高度
 * @param {number} quality - 压缩质量（0-1）
 * @returns {Promise<string>} 调整后的Base64图像
 */
export const resizeImage = (imageSrc, maxWidth = 800, maxHeight = 600, quality = 0.8) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      
      // 计算新尺寸
      let { width, height } = img
      
      if (width > height) {
        if (width > maxWidth) {
          height = (height * maxWidth) / width
          width = maxWidth
        }
      } else {
        if (height > maxHeight) {
          width = (width * maxHeight) / height
          height = maxHeight
        }
      }
      
      canvas.width = width
      canvas.height = height
      
      // 绘制调整后的图像
      ctx.drawImage(img, 0, 0, width, height)
      
      // 转换为Base64
      const resizedBase64 = canvas.toDataURL('image/jpeg', quality)
      resolve(resizedBase64)
    }
    img.onerror = reject
    img.src = imageSrc
  })
}

/**
 * 在Canvas上绘制图像
 * @param {HTMLCanvasElement} canvas - Canvas元素
 * @param {string} imageSrc - 图像源
 * @param {Object} options - 绘制选项
 * @returns {Promise<void>}
 */
export const drawImageOnCanvas = (canvas, imageSrc, options = {}) => {
  return new Promise((resolve, reject) => {
    const ctx = canvas.getContext('2d')
    const img = new Image()
    
    img.onload = () => {
      const { 
        x = 0, 
        y = 0, 
        width = canvas.width, 
        height = canvas.height,
        clearCanvas = true 
      } = options
      
      if (clearCanvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
      }
      
      ctx.drawImage(img, x, y, width, height)
      resolve()
    }
    
    img.onerror = reject
    img.src = imageSrc
  })
}

/**
 * 创建图像预览
 * @param {File} file - 图像文件
 * @param {number} maxSize - 预览最大尺寸
 * @returns {Promise<string>} 预览图像的Base64编码
 */
export const createImagePreview = async (file, maxSize = 300) => {
  try {
    const base64 = await fileToBase64(file)
    const resized = await resizeImage(base64, maxSize, maxSize, 0.7)
    return resized
  } catch (error) {
    console.error('创建图像预览失败:', error)
    throw error
  }
}

/**
 * 获取图像尺寸信息
 * @param {string} imageSrc - 图像源
 * @returns {Promise<Object>} 包含width和height的对象
 */
export const getImageDimensions = (imageSrc) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      resolve({
        width: img.naturalWidth,
        height: img.naturalHeight
      })
    }
    img.onerror = reject
    img.src = imageSrc
  })
}

/**
 * 验证图像文件
 * @param {File} file - 文件对象
 * @returns {Object} 验证结果
 */
export const validateImageFile = (file) => {
  const result = {
    valid: true,
    errors: []
  }
  
  // 检查文件类型
  if (!file.type.startsWith('image/')) {
    result.valid = false
    result.errors.push('文件类型必须是图像格式')
  }
  
  // 检查文件大小（10MB限制）
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    result.valid = false
    result.errors.push('文件大小不能超过10MB')
  }
  
  // 检查支持的格式
  const supportedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp']
  if (!supportedTypes.includes(file.type)) {
    result.valid = false
    result.errors.push('支持的格式：JPEG, PNG, GIF, BMP')
  }
  
  return result
}

/**
 * 绘制人体关键点
 * @param {CanvasRenderingContext2D} ctx - Canvas上下文
 * @param {Array} keypoints - 关键点数组 [x, y, confidence, ...]
 * @param {Object} options - 绘制选项
 */
export const drawBodyKeypoints = (ctx, keypoints, options = {}) => {
  const {
    pointColor = '#ff0000',
    pointRadius = 3,
    lineColor = '#00ff00',
    lineWidth = 2,
    confidenceThreshold = 0.1
  } = options
  
  // OpenPose身体关键点连接定义
  const bodyConnections = [
    [1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7],
    [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13],
    [1, 0], [0, 14], [14, 16], [0, 15], [15, 17]
  ]
  
  ctx.save()
  
  // 绘制骨架连接线
  ctx.strokeStyle = lineColor
  ctx.lineWidth = lineWidth
  
  bodyConnections.forEach(([startIdx, endIdx]) => {
    const startX = keypoints[startIdx * 3]
    const startY = keypoints[startIdx * 3 + 1]
    const startConf = keypoints[startIdx * 3 + 2]
    
    const endX = keypoints[endIdx * 3]
    const endY = keypoints[endIdx * 3 + 1]
    const endConf = keypoints[endIdx * 3 + 2]
    
    if (startConf > confidenceThreshold && endConf > confidenceThreshold) {
      ctx.beginPath()
      ctx.moveTo(startX, startY)
      ctx.lineTo(endX, endY)
      ctx.stroke()
    }
  })
  
  // 绘制关键点
  ctx.fillStyle = pointColor
  
  for (let i = 0; i < keypoints.length; i += 3) {
    const x = keypoints[i]
    const y = keypoints[i + 1]
    const confidence = keypoints[i + 2]
    
    if (confidence > confidenceThreshold) {
      ctx.beginPath()
      ctx.arc(x, y, pointRadius, 0, 2 * Math.PI)
      ctx.fill()
    }
  }
  
  ctx.restore()
}

/**
 * 绘制手部关键点
 * @param {CanvasRenderingContext2D} ctx - Canvas上下文
 * @param {Array} handKeypoints - 手部关键点数组
 * @param {Object} options - 绘制选项
 */
export const drawHandKeypoints = (ctx, handKeypoints, options = {}) => {
  const {
    pointColor = '#0000ff',
    pointRadius = 2,
    lineColor = '#00ffff',
    lineWidth = 1,
    confidenceThreshold = 0.1
  } = options
  
  // 手部关键点连接定义
  const handConnections = [
    // 拇指
    [0, 1], [1, 2], [2, 3], [3, 4],
    // 食指
    [0, 5], [5, 6], [6, 7], [7, 8],
    // 中指
    [0, 9], [9, 10], [10, 11], [11, 12],
    // 无名指
    [0, 13], [13, 14], [14, 15], [15, 16],
    // 小指
    [0, 17], [17, 18], [18, 19], [19, 20]
  ]
  
  ctx.save()
  
  handKeypoints.forEach(hand => {
    if (!hand || hand.length < 63) return // 21个点 * 3 = 63
    
    // 绘制手部连接线
    ctx.strokeStyle = lineColor
    ctx.lineWidth = lineWidth
    
    handConnections.forEach(([startIdx, endIdx]) => {
      const startX = hand[startIdx * 3]
      const startY = hand[startIdx * 3 + 1]
      const startConf = hand[startIdx * 3 + 2]
      
      const endX = hand[endIdx * 3]
      const endY = hand[endIdx * 3 + 1]
      const endConf = hand[endIdx * 3 + 2]
      
      if (startConf > confidenceThreshold && endConf > confidenceThreshold) {
        ctx.beginPath()
        ctx.moveTo(startX, startY)
        ctx.lineTo(endX, endY)
        ctx.stroke()
      }
    })
    
    // 绘制手部关键点
    ctx.fillStyle = pointColor
    
    for (let i = 0; i < hand.length; i += 3) {
      const x = hand[i]
      const y = hand[i + 1]
      const confidence = hand[i + 2]
      
      if (confidence > confidenceThreshold) {
        ctx.beginPath()
        ctx.arc(x, y, pointRadius, 0, 2 * Math.PI)
        ctx.fill()
      }
    }
  })
  
  ctx.restore()
}

/**
 * 绘制检测结果
 * @param {HTMLCanvasElement} canvas - Canvas元素
 * @param {Object} detectionResult - 检测结果
 * @param {Object} options - 绘制选项
 */
export const drawDetectionResult = (canvas, detectionResult, options = {}) => {
  const ctx = canvas.getContext('2d')
  
  if (detectionResult.keypoints) {
    detectionResult.keypoints.forEach(person => {
      // 绘制身体关键点
      if (person.body_keypoints && options.drawBody !== false) {
        drawBodyKeypoints(ctx, person.body_keypoints, options.bodyOptions)
      }
      
      // 绘制手部关键点
      if (person.hand_keypoints && options.drawHands !== false) {
        drawHandKeypoints(ctx, person.hand_keypoints, options.handOptions)
      }
    })
  }
}

/**
 * 清除Canvas并绘制背景图像
 * @param {HTMLCanvasElement} canvas - Canvas元素
 * @param {HTMLVideoElement|HTMLImageElement} source - 背景图像源
 */
export const clearAndDrawBackground = (canvas, source) => {
  const ctx = canvas.getContext('2d')
  
  // 设置Canvas尺寸
  if (source.videoWidth) {
    canvas.width = source.videoWidth
    canvas.height = source.videoHeight
  } else if (source.naturalWidth) {
    canvas.width = source.naturalWidth
    canvas.height = source.naturalHeight
  }
  
  // 清除并绘制背景
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height)
}

/**
 * 压缩图像
 * @param {string} imageSrc - 图像源
 * @param {number} quality - 压缩质量 (0-1)
 * @param {string} format - 输出格式
 * @returns {Promise<string>} 压缩后的图像
 */
export const compressImage = (imageSrc, quality = 0.8, format = 'image/jpeg') => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      
      canvas.width = img.width
      canvas.height = img.height
      
      ctx.drawImage(img, 0, 0)
      
      const compressedData = canvas.toDataURL(format, quality)
      resolve(compressedData)
    }
    img.onerror = reject
    img.src = imageSrc
  })
}

/**
 * 裁剪图像
 * @param {string} imageSrc - 图像源
 * @param {Object} cropArea - 裁剪区域 {x, y, width, height}
 * @returns {Promise<string>} 裁剪后的图像
 */
export const cropImage = (imageSrc, cropArea) => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      
      canvas.width = cropArea.width
      canvas.height = cropArea.height
      
      ctx.drawImage(
        img,
        cropArea.x, cropArea.y, cropArea.width, cropArea.height,
        0, 0, cropArea.width, cropArea.height
      )
      
      const croppedData = canvas.toDataURL('image/jpeg', 0.9)
      resolve(croppedData)
    }
    img.onerror = reject
    img.src = imageSrc
  })
}

export default {
  fileToBase64,
  base64ToBlob,
  resizeImage,
  drawImageOnCanvas,
  createImagePreview,
  getImageDimensions,
  validateImageFile,
  drawBodyKeypoints,
  drawHandKeypoints,
  drawDetectionResult,
  clearAndDrawBackground,
  compressImage,
  cropImage
} 