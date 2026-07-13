/**
 * camera.js - Guided multi-angle face capture for exam pre-registration.
 * Angle list comes from window.CAPTURE_ANGLES (set in register.html from
 * the server-side ANGLE_LABELS in schemas.py, so the count/order here
 * always matches what the backend expects) - falls back to the old
 * front/left/right set if that global isn't present for some reason.
 * Each angle gets its own preview thumbnail that can be retaken
 * individually. Final result is stored as a JSON array of base64
 * strings, in angle order, in #face_images_json.
 */
(function () {
    const ANGLE_DEFS = window.CAPTURE_ANGLES || [
        { key: "front", label: "Front" },
        { key: "left", label: "Left" },
        { key: "right", label: "Right" },
    ];
    const ANGLES = ANGLE_DEFS.map((a) => a.key);
    const ANGLE_LABELS = Object.fromEntries(ANGLE_DEFS.map((a) => [a.key, a.label]));

    const video = document.getElementById("camera-video");
    const canvas = document.getElementById("camera-canvas");
    const overlay = document.getElementById("camera-overlay");
    const startBtn = document.getElementById("start-camera-btn");
    const captureBtn = document.getElementById("capture-btn");
    const captureBtnLabel = document.getElementById("capture-btn-label");
    const submitBtn = document.getElementById("submit-btn");
    const hiddenField = document.getElementById("face_images_json");
    const thumbGrid = document.getElementById("thumb-grid");

    if (!video) return; // not on the registration page

    let stream = null;
    // captures[angle] = base64 dataUrl or null
    let captures = Object.fromEntries(ANGLES.map((a) => [a, null]));
    let targetAngle = ANGLES[0]; // which slot the next capture fills

    function nextEmptyAngle() {
        return ANGLES.find((a) => !captures[a]) || null;
    }

    function syncHiddenField() {
        const ordered = ANGLES.map((a) => captures[a]).filter(Boolean);
        hiddenField.value = JSON.stringify(ordered);
        submitBtn.disabled = ANGLES.some((a) => !captures[a]);
    }

    function updateThumb(angle) {
        const slot = thumbGrid.querySelector(`.thumb-slot[data-angle="${angle}"]`);
        if (!slot) return;
        const img = slot.querySelector(".thumb-image");
        const placeholder = slot.querySelector(".thumb-placeholder");
        const editBtn = slot.querySelector(".thumb-edit-btn");

        if (captures[angle]) {
            img.src = captures[angle];
            img.style.display = "block";
            placeholder.style.display = "none";
            editBtn.style.display = "flex";
            slot.classList.add("filled");
        } else {
            img.style.display = "none";
            placeholder.style.display = "flex";
            editBtn.style.display = "none";
            slot.classList.remove("filled");
        }
        slot.classList.toggle("targeted", angle === targetAngle && !captures[angle]);
    }

    function refreshUI() {
        ANGLES.forEach(updateThumb);
        if (targetAngle) {
            captureBtnLabel.textContent = captures[targetAngle]
                ? `Retake ${ANGLE_LABELS[targetAngle]}`
                : `Capture ${ANGLE_LABELS[targetAngle]}`;
            captureBtn.disabled = !stream;
        } else {
            captureBtnLabel.textContent = "All angles captured";
            captureBtn.disabled = true;
        }
        syncHiddenField();
    }

    async function startCamera(forAngle) {
        targetAngle = forAngle || nextEmptyAngle() || ANGLES[0];
        if (stream) {
            refreshUI();
            return;
        }
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
            video.srcObject = stream;
            overlay.style.display = "none";
            startBtn.style.display = "none";
            refreshUI();
        } catch (err) {
            overlay.innerHTML = '<i data-feather="alert-triangle"></i><span>Camera access denied or unavailable</span>';
            if (window.feather) feather.replace();
            console.error("Camera error:", err);
        }
    }

    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach((t) => t.stop());
            stream = null;
        }
        overlay.style.display = "flex";
        overlay.innerHTML = '<i data-feather="check-circle"></i><span>All angles captured</span>';
        startBtn.style.display = "inline-flex";
        startBtn.innerHTML = '<i data-feather="video"></i> Restart Camera';
        if (window.feather) feather.replace();
    }

    function captureFrame() {
        if (!stream || !targetAngle) return;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        captures[targetAngle] = canvas.toDataURL("image/jpeg", 0.85);

        const nextAngle = nextEmptyAngle();
        targetAngle = nextAngle;
        refreshUI();

        if (!nextAngle) {
            stopCamera();
        }
    }

    function retakeAngle(angle) {
        captures[angle] = null;
        if (!stream) {
            startCamera(angle);
        } else {
            targetAngle = angle;
            refreshUI();
        }
    }

    function reset() {
        captures = Object.fromEntries(ANGLES.map((a) => [a, null]));
        targetAngle = ANGLES[0];
        if (stream) {
            stream.getTracks().forEach((t) => t.stop());
            stream = null;
        }
        overlay.style.display = "flex";
        overlay.innerHTML = '<i data-feather="camera-off"></i><span>Camera not started</span>';
        startBtn.style.display = "inline-flex";
        startBtn.innerHTML = '<i data-feather="video"></i> Start Camera';
        refreshUI();
        if (window.feather) feather.replace();
    }

    startBtn.addEventListener("click", () => startCamera());
    captureBtn.addEventListener("click", captureFrame);
    thumbGrid.addEventListener("click", (e) => {
        const btn = e.target.closest(".thumb-edit-btn");
        if (btn) retakeAngle(btn.dataset.retake);
    });

    // Exposed so register_flow.js can reset the capture state if the
    // student cancels out of the "not registered" interstitial and
    // starts over with a different matric number.
    window.resetFaceCapture = reset;

    refreshUI();
})();
