/**
 * WebSocket管理工具类
 * 用于实时检测的WebSocket连接管理、自动重连和消息处理
 */

export class WebSocketManager {
  constructor(options = {}) {
    this.url = options.url || ''
    this.protocols = options.protocols || []
    this.reconnectInterval = options.reconnectInterval || 5000
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10
    this.heartbeatInterval = options.heartbeatInterval || 25000
    
    this.ws = null
    this.reconnectAttempts = 0
    this.isConnecting = false
    this.isManualClose = false
    this.messageQueue = []
    this.heartbeatTimer = null
    
    // 事件回调
    this.onOpen = options.onOpen || (() => {})
    this.onMessage = options.onMessage || (() => {})
    this.onClose = options.onClose || (() => {})
    this.onError = options.onError || (() => {})
    this.onReconnect = options.onReconnect || (() => {})
  }
  
  /**
   * 连接WebSocket
   * @param {string} url - WebSocket URL
   */
  connect(url) {
    if (url) {
      this.url = url
    }
    
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    
    this.isConnecting = true
    this.isManualClose = false
    
    try {
      this.ws = new WebSocket(this.url, this.protocols)
      this.setupEventListeners()
    } catch (error) {
      this.isConnecting = false
      this.onError(error)
    }
  }
  
  /**
   * 设置事件监听器
   */
  setupEventListeners() {
    this.ws.onopen = (event) => {
      this.isConnecting = false
      this.reconnectAttempts = 0
      
      // 发送队列中的消息
      this.flushMessageQueue()
      
      // 启动心跳
      this.startHeartbeat()
      
      this.onOpen(event)
    }
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        // 处理心跳响应
        if (data.type === 'pong' || data.type === 'heartbeat') {
          console.log('收到心跳响应:', data.type)
          return
        }
        
        this.onMessage(data, event)
      } catch (error) {
        this.onMessage(event.data, event)
      }
    }
    
    this.ws.onclose = (event) => {
      this.isConnecting = false
      this.stopHeartbeat()
      
      this.onClose(event)
      
      // 自动重连
      if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect()
      }
    }
    
    this.ws.onerror = (event) => {
      this.isConnecting = false
      this.onError(event)
    }
  }
  
  /**
   * 发送消息
   * @param {any} data - 要发送的数据
   */
  send(data) {
    const message = typeof data === 'string' ? data : JSON.stringify(data)
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(message)
    } else {
      // 连接未就绪时，将消息加入队列
      this.messageQueue.push(message)
    }
  }
  
  /**
   * 发送队列中的消息
   */
  flushMessageQueue() {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()
      this.ws.send(message)
    }
  }
  
  /**
   * 关闭连接
   * @param {number} code - 关闭代码
   * @param {string} reason - 关闭原因
   */
  close(code = 1000, reason = '') {
    this.isManualClose = true
    this.stopHeartbeat()
    
    if (this.ws) {
      this.ws.close(code, reason)
    }
  }
  
  /**
   * 安排重连
   */
  scheduleReconnect() {
    this.reconnectAttempts++
    
    setTimeout(() => {
      this.onReconnect(this.reconnectAttempts)
      this.connect()
    }, this.reconnectInterval)
  }
  
  /**
   * 启动心跳
   */
  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping', timestamp: Date.now() })
      }
    }, this.heartbeatInterval)
  }
  
  /**
   * 停止心跳
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
  
  /**
   * 获取连接状态
   */
  getReadyState() {
    return this.ws ? this.ws.readyState : WebSocket.CLOSED
  }
  
  /**
   * 检查是否已连接
   */
  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN
  }
  
  /**
   * 检查是否正在连接
   */
  isConnectingState() {
    return this.isConnecting || (this.ws && this.ws.readyState === WebSocket.CONNECTING)
  }
  
  /**
   * 重置重连计数
   */
  resetReconnectAttempts() {
    this.reconnectAttempts = 0
  }
  
  /**
   * 销毁WebSocket管理器
   */
  destroy() {
    this.close()
    this.messageQueue = []
    this.ws = null
  }
}

/**
 * 创建实时检测WebSocket连接
 * @param {string} clientId - 客户端ID
 * @param {Object} options - 连接选项
 * @returns {WebSocketManager} WebSocket管理器实例
 */
export const createRealtimeWebSocket = (clientId, options = {}) => {
  const {
    includeBody = true,
    includeHands = true,
    targetFps = 15,
    baseUrl = 'ws://localhost:8001'
  } = options
  
  const url = `${baseUrl}/api/ws/realtime/${clientId}?include_body=${includeBody}&include_hands=${includeHands}&target_fps=${targetFps}`
  
  return new WebSocketManager({
    url,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
    heartbeatInterval: 30000,
    ...options
  })
}

export default WebSocketManager 