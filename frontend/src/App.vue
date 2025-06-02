<template>
  <div id="app">
    <!-- 顶部导航 -->
    <HeaderNav 
      :current-tab="currentTab" 
      @tab-change="handleTabChange"
    />
    
    <!-- 主要演示区域 -->
    <main class="main-content">
      <!-- 图像检测 -->
      <ImageDemo v-show="currentTab === 'image'" />
      
      <!-- 视频处理 -->
      <VideoDemo v-show="currentTab === 'video'" />
      
      <!-- 实时检测 -->
      <RealtimeDemo v-show="currentTab === 'realtime'" />
    </main>
    
    <!-- 底部状态栏 -->
    <StatusBar />
  </div>
</template>

<script>
import { ref } from 'vue'
import HeaderNav from './components/HeaderNav.vue'
import ImageDemo from './components/ImageDemo.vue'
import VideoDemo from './components/VideoDemo.vue'
import RealtimeDemo from './components/RealtimeDemo.vue'
import StatusBar from './components/StatusBar.vue'

export default {
  name: 'App',
  components: {
    HeaderNav,
    ImageDemo,
    VideoDemo,
    RealtimeDemo,
    StatusBar
  },
  setup() {
    const currentTab = ref('image') // 默认显示图像检测
    
    const handleTabChange = (tab) => {
      currentTab.value = tab
    }
    
    return {
      currentTab,
      handleTabChange
    }
  }
}
</script><style scoped>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
</style>