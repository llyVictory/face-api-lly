import { reactive } from 'vue';

export const appState = reactive({
    currentStep: 0, // 0: Init, 1: Liveness, 2: DualCheck, 3: Success
    baseFaceDescriptor: null, // Float32Array from Step 1
    baseFaceImage: null, // Base64 image
    verificationQR: 'DEMO_CLASSROOM', // Expected QR content
    debugLog: [],

    log(msg) {
        console.log(`[App] ${msg}`);
        this.debugLog.unshift(`${new Date().toLocaleTimeString()} - ${msg}`);
        if (this.debugLog.length > 20) this.debugLog.pop();
    },

    reset() {
        this.currentStep = 0;
        this.baseFaceDescriptor = null;
        this.baseFaceImage = null;
        this.debugLog = [];
    }
});
