/**
 * 统一错误处理工具类
 * 用于错误分类、格式化和用户友好的错误提示
 */

import { ElMessage, ElNotification } from 'element-plus'

/**
 * 错误类型枚举
 */
export const ErrorTypes = {
  NETWORK: 'network',
  SERVER: 'server',
  CLIENT: 'client',
  VALIDATION: 'validation',
  PERMISSION: 'permission',
  TIMEOUT: 'timeout',
  UNKNOWN: 'unknown'
}

/**
 * 错误严重级别
 */
export const ErrorSeverity = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical'
}

/**
 * 错误处理器类
 */
export class ErrorHandler {
  constructor(options = {}) {
    this.enableLogging = options.enableLogging !== false
    this.enableNotification = options.enableNotification !== false
    this.logEndpoint = options.logEndpoint || null
  }
  
  /**
   * 处理错误
   * @param {Error|Object} error - 错误对象
   * @param {Object} context - 错误上下文信息
   * @returns {Object} 处理后的错误信息
   */
  handle(error, context = {}) {
    const errorInfo = this.analyzeError(error, context)
    
    // 记录错误日志
    if (this.enableLogging) {
      this.logError(errorInfo)
    }
    
    // 显示用户提示
    this.showUserFeedback(errorInfo)
    
    return errorInfo
  }
  
  /**
   * 分析错误类型和严重程度
   * @param {Error|Object} error - 错误对象
   * @param {Object} context - 错误上下文
   * @returns {Object} 错误分析结果
   */
  analyzeError(error, context) {
    const errorInfo = {
      type: ErrorTypes.UNKNOWN,
      severity: ErrorSeverity.MEDIUM,
      message: '发生未知错误',
      originalError: error,
      context,
      timestamp: new Date().toISOString(),
      userMessage: '',
      suggestions: []
    }
    
    // 网络错误
    if (error.code === 'NETWORK_ERROR' || error.message?.includes('Network Error')) {
      errorInfo.type = ErrorTypes.NETWORK
      errorInfo.severity = ErrorSeverity.HIGH
      errorInfo.message = '网络连接失败'
      errorInfo.userMessage = '网络连接失败，请检查网络设置'
      errorInfo.suggestions = [
        '检查网络连接是否正常',
        '确认服务器地址是否正确',
        '尝试刷新页面重试'
      ]
    }
    // HTTP响应错误
    else if (error.response) {
      errorInfo.type = ErrorTypes.SERVER
      const status = error.response.status
      
      if (status >= 400 && status < 500) {
        errorInfo.severity = ErrorSeverity.MEDIUM
        errorInfo.type = status === 401 || status === 403 ? ErrorTypes.PERMISSION : ErrorTypes.CLIENT
        
        switch (status) {
          case 400:
            errorInfo.message = '请求参数错误'
            errorInfo.userMessage = '请求参数有误，请检查输入内容'
            break
          case 401:
            errorInfo.message = '未授权访问'
            errorInfo.userMessage = '访问权限不足，请重新登录'
            break
          case 403:
            errorInfo.message = '禁止访问'
            errorInfo.userMessage = '没有访问权限'
            break
          case 404:
            errorInfo.message = '资源不存在'
            errorInfo.userMessage = '请求的资源不存在'
            break
          case 422:
            errorInfo.message = '数据验证失败'
            errorInfo.userMessage = '输入数据格式不正确'
            break
          default:
            errorInfo.message = `客户端错误 (${status})`
            errorInfo.userMessage = '请求处理失败，请检查输入内容'
        }
      } else if (status >= 500) {
        errorInfo.severity = ErrorSeverity.HIGH
        errorInfo.message = `服务器错误 (${status})`
        errorInfo.userMessage = '服务器暂时无法处理请求，请稍后重试'
        errorInfo.suggestions = [
          '稍后重试',
          '联系技术支持',
          '检查服务器状态'
        ]
      }
      
      // 提取详细错误信息
      if (error.response.data?.detail) {
        errorInfo.message += ': ' + error.response.data.detail
      }
    }
    // 请求超时
    else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      errorInfo.type = ErrorTypes.TIMEOUT
      errorInfo.severity = ErrorSeverity.MEDIUM
      errorInfo.message = '请求超时'
      errorInfo.userMessage = '请求处理时间过长，请稍后重试'
      errorInfo.suggestions = [
        '检查网络连接速度',
        '稍后重试',
        '尝试减小文件大小'
      ]
    }
    // 文件验证错误
    else if (error.type === 'validation') {
      errorInfo.type = ErrorTypes.VALIDATION
      errorInfo.severity = ErrorSeverity.LOW
      errorInfo.message = error.message || '数据验证失败'
      errorInfo.userMessage = error.message || '输入数据不符合要求'
      errorInfo.suggestions = error.suggestions || [
        '检查文件格式是否正确',
        '确认文件大小是否符合要求'
      ]
    }
    // WebSocket错误
    else if (error.type === 'websocket') {
      errorInfo.type = ErrorTypes.NETWORK
      errorInfo.severity = ErrorSeverity.MEDIUM
      errorInfo.message = 'WebSocket连接错误'
      errorInfo.userMessage = '实时连接中断，正在尝试重连'
      errorInfo.suggestions = [
        '检查网络连接',
        '等待自动重连',
        '刷新页面重试'
      ]
    }
    // 其他错误
    else {
      errorInfo.message = error.message || '发生未知错误'
      errorInfo.userMessage = '操作失败，请重试'
      errorInfo.suggestions = [
        '刷新页面重试',
        '检查网络连接',
        '联系技术支持'
      ]
    }
    
    return errorInfo
  }
  
  /**
   * 显示用户反馈
   * @param {Object} errorInfo - 错误信息
   */
  showUserFeedback(errorInfo) {
    if (!this.enableNotification) return
    
    const { severity, userMessage, suggestions } = errorInfo
    
    // 根据严重程度选择提示方式
    if (severity === ErrorSeverity.CRITICAL || severity === ErrorSeverity.HIGH) {
      ElNotification({
        title: '错误',
        message: this.formatUserMessage(userMessage, suggestions),
        type: 'error',
        duration: 8000,
        dangerouslyUseHTMLString: true
      })
    } else if (severity === ErrorSeverity.MEDIUM) {
      ElMessage({
        message: userMessage,
        type: 'error',
        duration: 5000
      })
    } else {
      ElMessage({
        message: userMessage,
        type: 'warning',
        duration: 3000
      })
    }
  }
  
  /**
   * 格式化用户消息
   * @param {string} message - 主要消息
   * @param {Array} suggestions - 建议列表
   * @returns {string} 格式化后的消息
   */
  formatUserMessage(message, suggestions = []) {
    let formatted = `<p><strong>${message}</strong></p>`
    
    if (suggestions.length > 0) {
      formatted += '<p>建议解决方案：</p><ul>'
      suggestions.forEach(suggestion => {
        formatted += `<li>${suggestion}</li>`
      })
      formatted += '</ul>'
    }
    
    return formatted
  }
  
  /**
   * 记录错误日志
   * @param {Object} errorInfo - 错误信息
   */
  logError(errorInfo) {
    // 控制台日志
    console.group(`🚨 Error [${errorInfo.type}] - ${errorInfo.severity}`)
    console.error('Message:', errorInfo.message)
    console.error('User Message:', errorInfo.userMessage)
    console.error('Context:', errorInfo.context)
    console.error('Original Error:', errorInfo.originalError)
    console.error('Timestamp:', errorInfo.timestamp)
    if (errorInfo.suggestions.length > 0) {
      console.info('Suggestions:', errorInfo.suggestions)
    }
    console.groupEnd()
    
    // 发送到日志服务器（如果配置了）
    if (this.logEndpoint) {
      this.sendToLogServer(errorInfo)
    }
  }
  
  /**
   * 发送错误日志到服务器
   * @param {Object} errorInfo - 错误信息
   */
  async sendToLogServer(errorInfo) {
    try {
      await fetch(this.logEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ...errorInfo,
          userAgent: navigator.userAgent,
          url: window.location.href
        })
      })
    } catch (error) {
      console.warn('Failed to send error log to server:', error)
    }
  }
}

/**
 * 默认错误处理器实例
 */
export const defaultErrorHandler = new ErrorHandler()

/**
 * 快捷错误处理函数
 * @param {Error|Object} error - 错误对象
 * @param {Object} context - 错误上下文
 * @returns {Object} 处理后的错误信息
 */
export const handleError = (error, context = {}) => {
  return defaultErrorHandler.handle(error, context)
}

/**
 * 创建验证错误
 * @param {string} message - 错误消息
 * @param {Array} suggestions - 建议列表
 * @returns {Object} 验证错误对象
 */
export const createValidationError = (message, suggestions = []) => {
  return {
    type: 'validation',
    message,
    suggestions
  }
}

/**
 * 创建网络错误
 * @param {string} message - 错误消息
 * @returns {Object} 网络错误对象
 */
export const createNetworkError = (message = '网络连接失败') => {
  return {
    code: 'NETWORK_ERROR',
    message
  }
}

/**
 * 创建WebSocket错误
 * @param {string} message - 错误消息
 * @returns {Object} WebSocket错误对象
 */
export const createWebSocketError = (message = 'WebSocket连接错误') => {
  return {
    type: 'websocket',
    message
  }
}

export default {
  ErrorHandler,
  ErrorTypes,
  ErrorSeverity,
  defaultErrorHandler,
  handleError,
  createValidationError,
  createNetworkError,
  createWebSocketError
} 