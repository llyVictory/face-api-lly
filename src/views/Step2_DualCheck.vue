<template>
  <div class="step-container">
    <Camera @ready="onCameraReady" @error="onCameraError" ref="cameraRef" />
    
    <div class="overlay-ui">
      <!-- Top Status Bar -->
      <div class="status-bar">
        <div class="step-badge">2/2 现场合拍</div>
        <div class="instruction">{{ instructionText }}</div>
      </div>

      <!-- Detection Indicators -->
      <div class="indicators">
        <div class="indicator" :class="{ ok: isFaceMatched }">
          <span class="icon">👤</span> 人脸: {{ faceStatus }}
        </div>
        <div class="indicator" :class="{ ok: isQrMatched }">
          <span class="icon">📍</span> 位置: {{ qrStatus }}
        </div>
      </div>

      <!-- Success Modal -->
      <div v-if="isSuccess" class="success-screen">
        <div class="success-content">
          <div class="checkmark">✔</div>
          <h2>签到成功</h2>
          <p>身份与位置核验通过</p>
          <button @click="resetApp">重新演示</button>
        </div>
      </div>

       <!-- Debug Info (Optional) -->
       <div v-if="debugMsg" class="debug-toast">{{ debugMsg }}</div>
       
       <!-- Success Counter Debug -->
       <div class="counter-debug">确认中: {{ successCounterDisplay }}/10</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue';
import Camera from '../components/Camera.vue';
import { faceEngine, api as faceapi } from '../logic/face';
import { scanQRCode } from '../logic/scanner';
import { appState } from '../state';

const cameraRef = ref(null);
const instructionText = ref("请与现场二维码同框合影");
const faceStatus = ref("未检测");
const qrStatus = ref("未检测");
const debugMsg = ref("");

const isFaceMatched = ref(false);
const isQrMatched = ref(false);
const isSuccess = ref(false);

let videoEl = null;
let canvasEl = null;
let loopId = null;
let successCounter = 0;
const successCounterDisplay = ref(0); // For UI display

const onCameraReady = ({ video, canvas }) => {
  videoEl = video;
  canvasEl = canvas;
  startDualLoop();
};

const onCameraError = (err) => {
  debugMsg.value = err.message;
};

const resetApp = () => {
    appState.reset();
}

const startDualLoop = async () => {
  const loop = async () => {
    if (!videoEl || videoEl.paused || videoEl.ended || isSuccess.value) return;

    // 1. Face Detection
    const detection = await faceEngine.detectSingleFace(videoEl);
    
    // 2. QR Detection
    // Draw current frame to canvas for QR scanning (and overlay clearing)
    const ctx = canvasEl.getContext('2d');
    ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
    
    // Scan QR from the canvas we just drew
    const qrResult = scanQRCode(ctx, canvasEl.width, canvasEl.height);

    // Clear canvas again to draw clean overlays
    // Actually, drawing the video frame is needed for scanQRCode in this implementation?
    // scanQRCode uses getImageData.
    // But we want to see the camera feed. The Camera component has a video element behind the canvas.
    // So we should CLEAR the canvas after scanning, so we can draw boxes on top of the video element.
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

    // --- Face Logic ---
    if (detection) {
      const dist = faceapi.euclideanDistance(detection.descriptor, appState.baseFaceDescriptor);
      debugMsg.value = `Distance: ${dist.toFixed(4)}`;
      
      const box = detection.detection.box;
      
      if (dist < 0.5) { // Match Threshold
         isFaceMatched.value = true;
         faceStatus.value = "匹配成功";
         drawBox(ctx, box, '#4CAF50', `我 (${dist.toFixed(2)})`);
      } else {
         isFaceMatched.value = false;
         faceStatus.value = "非本人";
         drawBox(ctx, box, '#F44336', `陌生人 (${dist.toFixed(2)})`);
      }
    } else {
      isFaceMatched.value = false;
      faceStatus.value = "未检测";
    }

    // --- QR Logic ---
    if (qrResult) {
      // visualization
      drawPoly(ctx, qrResult.location, '#2196F3');

      if (qrResult.data.includes(appState.verificationQR) || qrResult.data === 'DEMO_CLASSROOM') {
         isQrMatched.value = true;
         qrStatus.value = "位置正确";
      } else {
         isQrMatched.value = false;
         qrStatus.value = "位置错误";
      }
    } else {
      // isQrMatched.value = false; 
      // Keep true for a few frames to prevent flickering? No, strict for demo.
      isQrMatched.value = false;
      qrStatus.value = "未检测";
    }

    // --- Final Check ---
    if (isFaceMatched.value && isQrMatched.value) {
        successCounter++;
        successCounterDisplay.value = successCounter; // Update UI
        if (successCounter > 10) { // Reduced from 20 to 10 for faster trigger
            handleSuccess();
        }
    } else {
        successCounter = 0;
        successCounterDisplay.value = 0; // Reset UI
    }

    loopId = requestAnimationFrame(loop);
  };

  loop();
};

const drawBox = (ctx, box, color, label) => {
  const canvasWidth = ctx.canvas.width;
  
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(box.x, box.y, box.width, box.height);
  
  // Draw text in correct orientation (counter the CSS mirror)
  ctx.save();
  // Move to text position, flip horizontally, then draw
  const textX = box.x + box.width / 2;
  const textY = box.y - 10;
  ctx.translate(textX, textY);
  ctx.scale(-1, 1); // Flip horizontally to counter CSS mirror
  ctx.fillStyle = color;
  ctx.font = 'bold 16px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(label, 0, 0);
  ctx.restore();
};

const drawPoly = (ctx, loc, color) => {
  ctx.beginPath();
  ctx.lineWidth = 4;
  ctx.strokeStyle = color;
  ctx.moveTo(loc.topLeftCorner.x, loc.topLeftCorner.y);
  ctx.lineTo(loc.topRightCorner.x, loc.topRightCorner.y);
  ctx.lineTo(loc.bottomRightCorner.x, loc.bottomRightCorner.y);
  ctx.lineTo(loc.bottomLeftCorner.x, loc.bottomLeftCorner.y);
  ctx.lineTo(loc.topLeftCorner.x, loc.topLeftCorner.y);
  ctx.stroke();
};

const handleSuccess = () => {
    isSuccess.value = true;
    instructionText.value = "完成!";
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
  color: #2196F3; /* Blue for Step 2 */
  font-weight: bold;
  margin-bottom: 4px;
}

.instruction {
  font-size: 18px;
  color: white;
  font-weight: 500;
}

.indicators {
    position: absolute;
    bottom: 120px;
    width: 100%;
    display: flex;
    justify-content: center;
    gap: 20px;
}

.indicator {
    background: rgba(0,0,0,0.5);
    color: #ccc;
    padding: 10px 15px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid rgba(255,255,255,0.1);
    transition: all 0.3s;
}

.indicator.ok {
    background: rgba(76, 175, 80, 0.2);
    border-color: #4CAF50;
    color: #4CAF50;
}

.success-screen {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.85);
    pointer-events: auto;
    display: flex;
    justify-content: center;
    align-items: center;
    animation: fadeIn 0.5s ease;
}

.success-content {
    text-align: center;
    color: white;
}

.checkmark {
    width: 80px;
    height: 80px;
    background: #4CAF50;
    border-radius: 50%;
    font-size: 40px;
    line-height: 80px;
    margin: 0 auto 20px;
    box-shadow: 0 0 30px #4CAF50;
}

button {
    margin-top: 20px;
    padding: 10px 24px;
    background: white;
    color: black;
    border: none;
    border-radius: 20px;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
}

.debug-toast {
  position: absolute;
  top: 100px;
  right: 10px;
  color: yellow;
  font-family: monospace;
  font-size: 10px;
  background: rgba(0,0,0,0.5);
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.counter-debug {
  position: absolute;
  top: 130px;
  right: 10px;
  background: rgba(0, 0, 0, 0.7);
  color: #4CAF50;
  padding: 6px 12px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 14px;
}
</style>
