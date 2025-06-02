/**
 * 前端骨架绘制工具函数
 * 用于实时检测中的关键点可视化
 */

// OpenPose身体关键点连接定义（18个关键点）
const BODY_CONNECTIONS = [
  [1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7],    // 手臂
  [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13], // 躯干和腿
  [1, 0], [0, 14], [14, 16], [0, 15], [15, 17]        // 头部
]

// 身体关键点颜色配置
const BODY_COLORS = [
  [255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], 
  [170, 255, 0], [85, 255, 0], [0, 255, 0], [0, 255, 85], 
  [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], 
  [0, 0, 255], [85, 0, 255], [170, 0, 255], [255, 0, 255], 
  [255, 0, 170], [255, 0, 85]
]

// 手部关键点连接定义（21个关键点）
const HAND_CONNECTIONS = [
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

/**
 * 绘制身体骨架
 * @param {CanvasRenderingContext2D} ctx - Canvas上下文
 * @param {Array} candidate - 关键点候选数组
 * @param {Array} subset - 人体连接数组
 * @param {Object} options - 绘制选项
 */
export const drawBodySkeleton = (ctx, candidate, subset, options = {}) => {
  const {
    pointRadius = 4,
    lineWidth = 3,
    confidenceThreshold = 0.1,
    alpha = 0.8
  } = options

  if (!candidate || !subset || candidate.length === 0 || subset.length === 0) {
    return
  }

  ctx.save()
  ctx.globalAlpha = alpha

  // 绘制骨架连接线
  ctx.lineWidth = lineWidth
  
  for (let i = 0; i < BODY_CONNECTIONS.length; i++) {
    const [startIdx, endIdx] = BODY_CONNECTIONS[i]
    const color = BODY_COLORS[i] || [255, 255, 255]
    
    for (let n = 0; n < subset.length; n++) {
      const startCandidateIdx = subset[n][startIdx]
      const endCandidateIdx = subset[n][endIdx]
      
      if (startCandidateIdx === -1 || endCandidateIdx === -1) continue
      
      const startPoint = candidate[startCandidateIdx]
      const endPoint = candidate[endCandidateIdx]
      
      if (!startPoint || !endPoint) continue
      
      const [startX, startY, startConf] = startPoint
      const [endX, endY, endConf] = endPoint
      
      if (startConf > confidenceThreshold && endConf > confidenceThreshold) {
        ctx.strokeStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`
        ctx.beginPath()
        ctx.moveTo(startX, startY)
        ctx.lineTo(endX, endY)
        ctx.stroke()
      }
    }
  }

  // 绘制关键点
  for (let i = 0; i < candidate.length; i++) {
    const [x, y, confidence] = candidate[i]
    
    if (confidence > confidenceThreshold) {
      const colorIdx = i % BODY_COLORS.length
      const color = BODY_COLORS[colorIdx]
      
      ctx.fillStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`
      ctx.beginPath()
      ctx.arc(x, y, pointRadius, 0, 2 * Math.PI)
      ctx.fill()
    }
  }

  ctx.restore()
}

/**
 * 绘制手部骨架
 * @param {CanvasRenderingContext2D} ctx - Canvas上下文
 * @param {Array} handPeaks - 手部关键点数组
 * @param {Object} options - 绘制选项
 */
export const drawHandSkeleton = (ctx, handPeaks, options = {}) => {
  const {
    pointRadius = 2,
    lineWidth = 2,
    confidenceThreshold = 0.1,
    leftHandColor = [0, 255, 0],   // 绿色
    rightHandColor = [0, 0, 255],  // 蓝色
    alpha = 0.8
  } = options

  if (!handPeaks || handPeaks.length === 0) {
    return
  }

  ctx.save()
  ctx.globalAlpha = alpha
  ctx.lineWidth = lineWidth

  handPeaks.forEach((hand, handIndex) => {
    if (!hand.peaks || hand.peaks.length === 0) return
    
    const peaks = hand.peaks
    const isLeft = hand.is_left
    const color = isLeft ? leftHandColor : rightHandColor
    
    // 绘制手部连接线
    ctx.strokeStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`
    
    for (const [startIdx, endIdx] of HAND_CONNECTIONS) {
      if (startIdx * 3 + 2 >= peaks.length || endIdx * 3 + 2 >= peaks.length) continue
      
      const startX = peaks[startIdx * 3]
      const startY = peaks[startIdx * 3 + 1]
      const startConf = peaks[startIdx * 3 + 2]
      
      const endX = peaks[endIdx * 3]
      const endY = peaks[endIdx * 3 + 1]
      const endConf = peaks[endIdx * 3 + 2]
      
      if (startConf > confidenceThreshold && endConf > confidenceThreshold) {
        ctx.beginPath()
        ctx.moveTo(startX, startY)
        ctx.lineTo(endX, endY)
        ctx.stroke()
      }
    }

    // 绘制手部关键点
    ctx.fillStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`
    
    for (let i = 0; i < peaks.length; i += 3) {
      const x = peaks[i]
      const y = peaks[i + 1]
      const confidence = peaks[i + 2]
      
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
 * 绘制完整的检测结果
 * @param {CanvasRenderingContext2D} ctx - Canvas上下文
 * @param {Object} detectionResults - 检测结果对象
 * @param {Object} options - 绘制选项
 */
export const drawDetectionResults = (ctx, detectionResults, options = {}) => {
  const {
    drawBody = true,
    drawHands = true,
    bodyOptions = {},
    handOptions = {}
  } = options

  // 绘制身体骨架
  if (drawBody && detectionResults.body) {
    const { candidate, subset } = detectionResults.body
    if (candidate && subset) {
      drawBodySkeleton(ctx, candidate, subset, bodyOptions)
    }
  }

  // 绘制手部骨架
  if (drawHands && detectionResults.hands) {
    const { hands_data } = detectionResults.hands
    if (hands_data && hands_data.length > 0) {
      drawHandSkeleton(ctx, hands_data, handOptions)
    }
  }
}

/**
 * 获取默认绘制选项
 * @returns {Object} 默认选项
 */
export const getDefaultDrawOptions = () => ({
  drawBody: true,
  drawHands: true,
  bodyOptions: {
    pointRadius: 4,
    lineWidth: 3,
    confidenceThreshold: 0.1,
    alpha: 0.8
  },
  handOptions: {
    pointRadius: 2,
    lineWidth: 2,
    confidenceThreshold: 0.1,
    leftHandColor: [0, 255, 0],
    rightHandColor: [0, 0, 255],
    alpha: 0.8
  }
})

export default {
  drawBodySkeleton,
  drawHandSkeleton,
  drawDetectionResults,
  getDefaultDrawOptions
} 