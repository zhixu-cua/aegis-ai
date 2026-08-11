import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url: string) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const messageHandlers = ref<((data: any) => void)[]>([])
  
  const connect = () => {
    const token = localStorage.getItem('satoken') || localStorage.getItem('token')
    const baseUrl = import.meta.env.VITE_WS_BASE_URL || `ws://${window.location.host}`
    const wsUrl = `${baseUrl}${url}?token=${token}`
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      isConnected.value = true
      console.log('WebSocket 已连接')
    }
    
    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messageHandlers.value.forEach(handler => handler(data))
      } catch (e) {
        console.error('WebSocket 消息解析失败', e)
      }
    }
    
    ws.value.onclose = () => {
      isConnected.value = false
      console.log('WebSocket 已断开')
      // 自动重连
      setTimeout(connect, 3000)
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket 错误', error)
    }
  }
  
  const onMessage = (handler: (data: any) => void) => {
    messageHandlers.value.push(handler)
  }
  
  const sendMessage = (data: any) => {
    if (ws.value && isConnected.value) {
      ws.value.send(JSON.stringify(data))
    }
  }
  
  const close = () => {
    if (ws.value) {
      ws.value.close()
    }
  }
  
  onMounted(connect)
  onUnmounted(close)
  
  return { isConnected, sendMessage, onMessage, close }
}
