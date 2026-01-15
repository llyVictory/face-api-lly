<template>
  <div class="app-container">
    <transition name="fade" mode="out-in">
      <div v-if="appState.currentStep === 0" class="welcome-screen" key="step0">
        <div class="hero-content">
          <h1>智能签到 Demo</h1>
          <p class="subtitle">AI Face Anti-spoofing + Location Check</p>
          
          <div class="features">
            <div class="feat">👁️ 活体检测</div>
            <div class="feat">📍 现场合拍</div>
          </div>

          <button class="start-btn" @click="startDemo" :disabled="loading">
            {{ loading ? '初始化中...' : '开始验证' }}
          </button>
          
          <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
        </div>
      </div>

      <Step1_Liveness v-else-if="appState.currentStep === 1" key="step1" />
      
      <Step2_DualCheck v-else-if="appState.currentStep === 2" key="step2" />
    </transition>
    <DebugQR />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { appState } from './state';
import Step1_Liveness from './views/Step1_Liveness.vue';
import Step2_DualCheck from './views/Step2_DualCheck.vue';
import DebugQR from './components/DebugQR.vue';
import { faceEngine } from './logic/face';

const loading = ref(false);
const errorMsg = ref("");

const startDemo = async () => {
  loading.value = true;
  errorMsg.value = "";
  try {
    // Permission check usually happens when mounting the Camera component, 
    // but we can warm up models here.
    await faceEngine.loadModels();
    appState.currentStep = 1;
  } catch (err) {
    errorMsg.value = "加载失败: " + err.message;
  } finally {
    loading.value = false;
  }
};
</script>

<style>
/* Global Resets */
:root {
  font-family: 'Inter', system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  color-scheme: dark;
}

body {
  margin: 0;
  background: #111;
  color: #fff;
  overflow: hidden; /* Prevent scrolling during camera view */
}

.app-container {
  width: 100vw;
  height: 100vh;
}

.welcome-screen {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
}

.hero-content {
  text-align: center;
  padding: 20px;
}

h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
  background: -webkit-linear-gradient(#eee, #333);
  -webkit-background-clip: text;
  /* -webkit-text-fill-color: transparent; */
  color: white;
  text-shadow: 0 0 20px rgba(255,255,255,0.3);
}

.subtitle {
  color: #88bece;
  margin-bottom: 2rem;
  font-weight: 300;
}

.features {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 3rem;
}

.feat {
  background: rgba(255,255,255,0.1);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 0.9rem;
  border: 1px solid rgba(255,255,255,0.1);
}

.start-btn {
  background: #2196F3;
  color: white;
  border: none;
  padding: 16px 40px;
  font-size: 1.2rem;
  font-weight: 600;
  border-radius: 50px;
  cursor: pointer;
  box-shadow: 0 0 20px rgba(33, 150, 243, 0.4);
  transition: transform 0.2s, box-shadow 0.2s;
}

.start-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 0 30px rgba(33, 150, 243, 0.6);
}

.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin-top: 20px;
  color: #ff6b6b;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
