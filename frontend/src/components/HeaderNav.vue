<template>
  <header class="header-nav">
    <div class="container">
      <!-- 项目标题 -->
      <div class="title">
        <h1>PyTorch OpenPose Web系统</h1>
        <span class="subtitle">人体姿态检测 - 答辩演示</span>
      </div>
      
      <!-- 功能标签导航 -->
      <nav class="nav-tabs">
        <el-tabs 
          v-model="activeTab" 
          @tab-change="handleTabChange"
          class="demo-tabs"
        >
          <el-tab-pane label="图像检测" name="image">
            <template #label>
              <el-icon><Picture /></el-icon>
              图像检测
            </template>
          </el-tab-pane>
          
          <el-tab-pane label="视频处理" name="video">
            <template #label>
              <el-icon><VideoPlay /></el-icon>
              视频处理
            </template>
          </el-tab-pane>
          
          <el-tab-pane label="实时检测" name="realtime">
            <template #label>
              <el-icon><Camera /></el-icon>
              实时检测
            </template>
          </el-tab-pane>
        </el-tabs>
      </nav>
    </div>
  </header>
</template>

<script>
import { ref, watch } from 'vue'
import { Picture, VideoPlay, Camera } from '@element-plus/icons-vue'

export default {
  name: 'HeaderNav',
  components: {
    Picture,
    VideoPlay, 
    Camera
  },
  props: {
    currentTab: {
      type: String,
      default: 'image'
    }
  },
  emits: ['tab-change'],
  setup(props, { emit }) {
    const activeTab = ref(props.currentTab)    
    // 监听外部tab变化
    watch(() => props.currentTab, (newTab) => {
      activeTab.value = newTab
    })
    
    const handleTabChange = (tabName) => {
      emit('tab-change', tabName)
    }
    
    return {
      activeTab,
      handleTabChange
    }
  }
}
</script>

<style scoped>
.header-nav {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px 0;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
}

.subtitle {
  font-size: 14px;
  opacity: 0.9;
}

.nav-tabs {
  min-width: 400px;
}

:deep(.el-tabs__header) {
  margin: 0;
}

:deep(.el-tabs__nav-wrap::after) {
  display: none;
}

:deep(.el-tabs__item) {
  color: rgba(255,255,255,0.8);
  font-weight: 500;
}

:deep(.el-tabs__item.is-active) {
  color: white;
}
</style>