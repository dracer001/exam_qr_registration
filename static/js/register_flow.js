/**
 * register_flow.js - Drives registration through:
 *   matric entry -> lookup ->
 *     already registered -> submit form straight away (server redirects to success)
 *     registered on course roster -> confirmed card + face capture
 *     not on course roster -> "not registered" interstitial -> Cancel (back to matric)
 *                                                             -> Proceed Anyway (confirmed card + face capture, flagged)
 */
(function () {
    const stepMatric = document.getElementById("step-matric");
    const stepNotRegistered = document.getElementById("step-not-registered");
    const form = document.getElementById("registration-form");

    if (!stepMatric || !form) return; // not on the registration page

    const matricInput = document.getElementById("matric_number");
    const lookupBtn = document.getElementById("lookup-btn");
    const lookupError = document.getElementById("lookup-error");

    const notRegisteredText = document.getElementById("not-registered-text");
    const notRegisteredCancelBtn = document.getElementById("not-registered-cancel-btn");
    const notRegisteredProceedBtn = document.getElementById("not-registered-proceed-btn");

    const confirmedMatricField = document.getElementById("confirmed-matric");
    const proceedAnywayField = document.getElementById("proceed-anyway-flag");
    const confirmAvatar = document.getElementById("confirm-avatar");
    const confirmName = document.getElementById("confirm-name");
    const confirmMeta = document.getElementById("confirm-meta");
    const proceedAnywayBanner = document.getElementById("proceed-anyway-banner");

    let pendingCandidate = null;

    function initials(fullName) {
        return (fullName || "").split(" ").map((w) => w[0] || "").join("").toUpperCase().slice(0, 2);
    }

    function showStep(step) {
        [stepMatric, stepNotRegistered, form].forEach((el) => (el.style.display = "none"));
        step.style.display = step === form ? "block" : "flex";
    }

    function showConfirmedForm(candidate, proceedAnyway) {
        confirmedMatricField.value = candidate.matric_no;
        proceedAnywayField.value = proceedAnyway ? "1" : "0";
        confirmAvatar.textContent = initials(candidate.full_name);
        confirmName.textContent = candidate.full_name;
        confirmMeta.textContent = `${candidate.matric_no} · ${candidate.department}, ${candidate.level}`;
        proceedAnywayBanner.style.display = proceedAnyway ? "flex" : "none";
        showStep(form);
        if (window.feather) feather.replace();
    }

    async function doLookup() {
        const matric = matricInput.value.trim();
        lookupError.style.display = "none";
        if (!matric) return;

        lookupBtn.disabled = true;
        try {
            const resp = await fetch(window.REGISTER_LOOKUP_URL, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ matric_number: matric }),
            });
            const data = await resp.json();

            if (data.result === "registered" || data.result === "already_registered") {
                pendingCandidate = data.candidate;
                showConfirmedForm(data.candidate, false);
            } else if (data.result === "not_registered") {
                pendingCandidate = data.candidate;
                notRegisteredText.textContent = data.message || "You are not registered for this course.";
                showStep(stepNotRegistered);
                if (window.feather) feather.replace();
            } else {
                lookupError.textContent = data.message || "No student record found for that matric number.";
                lookupError.style.display = "flex";
                if (window.feather) feather.replace();
            }
        } finally {
            lookupBtn.disabled = false;
        }
    }

    lookupBtn.addEventListener("click", doLookup);
    matricInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") doLookup();
    });

    notRegisteredCancelBtn.addEventListener("click", () => {
        pendingCandidate = null;
        matricInput.value = "";
        showStep(stepMatric);
        matricInput.focus();
    });

    notRegisteredProceedBtn.addEventListener("click", () => {
        if (!pendingCandidate) return;
        showConfirmedForm(pendingCandidate, true);
    });

    showStep(stepMatric);
})();
