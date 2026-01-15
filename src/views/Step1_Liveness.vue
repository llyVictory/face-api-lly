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

      <!-- Debug Display -->
      <div class="debug-ear">{{ debugKey }}: {{ debugVal }}</div>
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
const debugKey = ref("Init");
const debugVal = ref("--");
let videoEl = null;
let canvasEl = null;
let loopId = null;

// Logic State
let actionQueue = []; // Queue of actions
let currentAction = ''; // 'blink' or 'mouth'
let isActionPending = false; // tracked state
let isProcessingAction = false; // Lock to prevent rapid-fire triggering

// Thresholds
const BLINK_CLOSE_THRESH = 0.28; 
const BLINK_OPEN_THRESH = 0.30;
const MOUTH_OPEN_THRESH = 0.40; 
const MOUTH_CLOSE_THRESH = 0.20; 

const onCameraReady = ({ video, canvas }) => {
  videoEl = video;
  canvasEl = canvas;
  
  if (Math.random() > 0.5) {
      actionQueue = ['blink', 'mouth'];
  } else {
      actionQueue = ['mouth', 'blink'];
  }
  
  nextAction(); 
  startDetectionLoop();
};

const nextAction = () => {
    if (actionQueue.length === 0) {
        currentAction = 'done';
        return;
    }
    
    currentAction = actionQueue.shift();
    isActionPending = false;
    isProcessingAction = false; // Unlock
    
    if (currentAction === 'blink') {
        instructionText.value = "动作 1/2: 请眨眨眼";
        debugKey.value = "EAR";
    } else if (currentAction === 'mouth') {
        instructionText.value = "动作 2/2: 请张张嘴";
        debugKey.value = "MAR";
    }
};
// ... (onCameraError kept same)

const startDetectionLoop = async () => {
  // ... (Model loading kept same)
  if (!faceEngine.modelsLoaded) {
      // ...
      await faceEngine.loadModels();
      // ...
  }

  const loop = async () => {
    if (!videoEl || videoEl.paused || videoEl.ended || isSuccess.value) return;

    const detection = await faceEngine.detectSingleFace(videoEl);
    const ctx = canvasEl.getContext('2d');
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

    if (detection && !isProcessingAction && currentAction !== 'done') {
      isFaceDetected.value = true;
      const landmarks = detection.landmarks;
      
      const leftEAR = faceEngine.calculateEAR(landmarks.getLeftEye());
      const rightEAR = faceEngine.calculateEAR(landmarks.getRightEye());
      const avgEAR = (leftEAR + rightEAR) / 2;
      const mar = faceEngine.calculateMAR(landmarks.getMouth());

      if (currentAction === 'blink') {
          debugVal.value = avgEAR.toFixed(3);
          
          if (avgEAR < BLINK_CLOSE_THRESH) {
            if (!isActionPending) {
              isActionPending = true; 
              feedbackMsg.value = "检测到闭眼...";
            }
          } else {
            if (isActionPending && avgEAR > BLINK_OPEN_THRESH) {
              handleActionSuccess("眨眼成功!");
            }
          }

      } else if (currentAction === 'mouth') {
           debugVal.value = mar.toFixed(3);
          
          if (mar > MOUTH_OPEN_THRESH) {
              if (!isActionPending) {
                  isActionPending = true; 
                  feedbackMsg.value = "检测到张嘴...";
              }
          } else {
              if (isActionPending && mar < MOUTH_CLOSE_THRESH) {
                  handleActionSuccess("张嘴成功!");
              }
          }
      }
    } else if (!detection) {
      isFaceDetected.value = false;
      feedbackMsg.value = currentAction === 'done' ? "准备跳转..." : "未检测到人脸";
    }

    loopId = requestAnimationFrame(loop);
  };

  loop();
};

const handleActionSuccess = (msg) => {
    isProcessingAction = true; // Lock immediately
    feedbackMsg.value = msg;
    isActionPending = false;
    
    // Check if this was the last action locally before waiting
    // (Actually nextAction logic handles queue)
    
    setTimeout(() => {
        nextAction();
        if (currentAction === 'done') {
             // Need detection for capture? triggerSuccess saves the last detection logic
             // But loop continues. We can capture in triggerSuccess using videoEl directly.
             // We pass 'null' for detection since triggerSuccess recalculates or we just capture video frame.
             // Wait, triggerSuccess used 'detection.descriptor'.
             // We need to capture descriptor at the END.
             // Let's capture verification descriptor NOW or at end?
             // Better capture at end of ALL actions.
             
             // To be safe, let's grab a fresh detection or use current flow.
             // Since loop continues, next frame will catch 'done' and we can trigger.
             // BUT triggerSuccess stops loop.
             
             // Simplest: Call a specific finalizer that gets one last clear frame.
             finalizeStep1();
        }
    }, 1500); // 1.5s delay to ensure user sees "Success" message and resets face
};

const finalizeStep1 = async () => {
    instructionText.value = "活体检测通过!";
    // Find one last good face for the descriptor
    let detection = await faceEngine.detectSingleFace(videoEl);
    if (!detection) {
        // Retry a few times if lost
        detection = await faceEngine.detectSingleFace(videoEl);
    }
    
    if (detection) {
        triggerSuccess(detection);
    } else {
        // Edge case: face lost right at the end. 
        // Just Restart capture or use loop to wait?
        // Let's just try to call triggerSuccess. if it needs detection..
        // Re-use logic.
        alert("请保持人脸在画面中");
        isProcessingAction = false; // Unlock to try again to capture
        currentAction = 'done'; // force done state? No, need to re-trigger.
        // Actually if face is lost, user might be confused.
        // Let's just reset to done state and let loop catch a face?
        // No, 'done' state stops loop logic in my code above.
        
        // Let's change loop logic to: if done, capture and finish.
    }
};

const triggerSuccess = async (detection) => {
  isSuccess.value = true;
  instructionText.value = "动作验证通过!";
  feedbackMsg.value = "正在截取...";
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
</style>
