<template>
  <div class="step-container">
    <Camera @ready="onCameraReady" @error="onCameraError" ref="cameraRef" />
    
    <div class="overlay-ui">
      <!-- Top Status Bar -->
      <div class="status-bar">
        <div class="step-badge">1/2 活体验证</div>
        <div class="instruction">{{ instructionText }}</div>
      </div>

      <!-- Face Guide Frame -->
      <div class="face-frame" :class="{ 'active': isFaceDetected, 'success': isSuccess }">
        <div class="corner tl"></div>
        <div class="corner tr"></div>
        <div class="corner bl"></div>
        <div class="corner br"></div>
        <div class="scan-line" v-if="isFaceDetected && !isSuccess"></div>
      </div>

      <!-- Feedback Toast -->
      <div v-if="feedbackMsg" class="feedback-toast">{{ feedbackMsg }}</div>

      <!-- Debug EAR Display -->
      <div class="debug-ear">EAR: {{ debugEAR }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue';
import Camera from '../components/Camera.vue';
import { faceEngine } from '../logic/face';
import { appState } from '../state';

const cameraRef = ref(null);
const isFaceDetected = ref(false);
const isSuccess = ref(false);
const instructionText = ref("请正对屏幕，保持静止");
const feedbackMsg = ref("");
const debugEAR = ref("--");
let videoEl = null;
let canvasEl = null;
let loopId = null;

// Logic State
let blinkCount = 0;
let isBlinking = false;
const BLINK_THRESHOLD = 0.285; // EAR value (lowered for easier detection)
const OPEN_THRESHOLD = 0.30; // EAR value to confirm eyes opened again

const onCameraReady = ({ video, canvas }) => {
  videoEl = video;
  canvasEl = canvas;
  startDetectionLoop();
};

const onCameraError = (err) => {
  feedbackMsg.value = "摄像头启动失败: " + err.message;
};

const startDetectionLoop = async () => {
  // Ensure models are loaded
  if (!faceEngine.modelsLoaded) {
    feedbackMsg.value = "正在加载AI模型...";
    await faceEngine.loadModels();
    feedbackMsg.value = "";
  }

  instructionText.value = "请眨眨眼 (Blink Eyes)";

  const loop = async () => {
    if (!videoEl || videoEl.paused || videoEl.ended) return;

    const detection = await faceEngine.detectSingleFace(videoEl);
    
    // Clear canvas
    const ctx = canvasEl.getContext('2d');
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

    if (detection) {
      isFaceDetected.value = true;
      
      // Draw landmarks for debugging/cool effect
      // faceapi.draw.drawFaceLandmarks(canvasEl, detection); // Optional: simplified draw

      // Liveness Check: Blink
      const landmarks = detection.landmarks;
      const leftEye = landmarks.getLeftEye();
      const rightEye = landmarks.getRightEye();
      
      const leftEAR = faceEngine.calculateEAR(leftEye);
      const rightEAR = faceEngine.calculateEAR(rightEye);
      const avgEAR = (leftEAR + rightEAR) / 2;

      // Update debug display
      debugEAR.value = avgEAR.toFixed(3);

      if (avgEAR < BLINK_THRESHOLD) {
        if (!isBlinking) {
          isBlinking = true; // Eyes closed
          feedbackMsg.value = "检测到闭眼...";
        }
      } else {
        if (isBlinking && avgEAR > OPEN_THRESHOLD) {
          // Eyes opened again -> Blink detected
          isBlinking = false;
          blinkCount++;
          feedbackMsg.value = "捕捉到眨眼动作!";
          
          if (blinkCount >= 1) { // Just 1 blink for demo speed
            handleSuccess(detection);
            return; // Stop loop
          }
        }
      }

    } else {
      isFaceDetected.value = false;
    }

    loopId = requestAnimationFrame(loop);
  };

  loop();
};

const handleSuccess = async (detection) => {
  isSuccess.value = true;
  instructionText.value = "验证通过!";
  cancelAnimationFrame(loopId);

  // Use the FULL detection descriptor (already computed in detectSingleFace)
  appState.baseFaceDescriptor = new Float32Array(detection.descriptor);
  
  // Capture Image
  const captureCanvas = document.createElement('canvas');
  captureCanvas.width = videoEl.videoWidth;
  captureCanvas.height = videoEl.videoHeight;
  captureCanvas.getContext('2d').drawImage(videoEl, 0, 0);
  appState.baseFaceImage = captureCanvas.toDataURL('image/jpeg');

  setTimeout(() => {
    appState.currentStep = 2; // Go to Step 2
  }, 1000);
};

// Manual skip for demo purposes
const manualSkip = async () => {
  feedbackMsg.value = "手动跳过，正在抓取人脸...";
  
  // Try to get current detection
  const detection = await faceEngine.detectSingleFace(videoEl);
  if (detection) {
    handleSuccess(detection);
  } else {
    feedbackMsg.value = "未检测到人脸，请确保脸部在画面中";
  }
};

onUnmounted(() => {
  if (loopId) cancelAnimationFrame(loopId);
});
</script>

<style scoped>
.step-container {
  width: 100vw;
  height: 100vh;
  position: relative;
  background: black;
}

.overlay-ui {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.status-bar {
  margin-top: 40px;
  background: rgba(0, 0, 0, 0.6);
  padding: 10px 20px;
  border-radius: 30px;
  backdrop-filter: blur(10px);
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.step-badge {
  font-size: 12px;
  color: #4CAF50;
  font-weight: bold;
  margin-bottom: 4px;
}

.instruction {
  font-size: 18px;
  color: white;
  font-weight: 500;
}

.face-frame {
  margin-top: 60px;
  width: 280px;
  height: 380px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 160px; /* Oval shape */
  position: relative;
  transition: all 0.3s ease;
}

.face-frame.active {
  border-color: #2196F3;
  box-shadow: 0 0 20px rgba(33, 150, 243, 0.5);
}

.face-frame.success {
  border-color: #4CAF50;
  box-shadow: 0 0 30px rgba(76, 175, 80, 0.8);
}

/* Corner Accents */
.corner {
  position: absolute;
  width: 20px;
  height: 20px;
  border: 4px solid transparent;
}
.tl { top: -2px; left: -2px; border-top-color: #fff; border-left-color: #fff; border-radius: 20px 0 0 0; }
.tr { top: -2px; right: -2px; border-top-color: #fff; border-right-color: #fff; border-radius: 0 20px 0 0; }
.bl { bottom: -2px; left: -2px; border-bottom-color: #fff; border-left-color: #fff; border-radius: 0 0 0 20px; }
.br { bottom: -2px; right: -2px; border-bottom-color: #fff; border-right-color: #fff; border-radius: 0 0 20px 0; }

.active .corner { border-color: #2196F3; }
.success .corner { border-color: #4CAF50; }

.scan-line {
  width: 100%;
  height: 4px;
  background: #2196F3;
  position: absolute;
  top: 0;
  animation: scan 2s linear infinite;
  opacity: 0.7;
  box-shadow: 0 0 10px #2196F3;
}

@keyframes scan {
  0% { top: 10%; opacity: 0; }
  10% { opacity: 1; }
  90% { opacity: 1; }
  100% { top: 90%; opacity: 0; }
}

.feedback-toast {
  position: absolute;
  bottom: 100px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.debug-ear {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.6);
  color: #4CAF50;
  padding: 6px 12px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 14px;
}

.skip-btn {
  position: absolute;
  bottom: 40px;
  background: rgba(255, 152, 0, 0.8);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  pointer-events: auto;
}
</style>
