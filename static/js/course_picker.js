/**
 * course_picker.js - Type-to-search course selector. Filters
 * window.COURSES_DATA client-side (course_code, title, lecturer_name)
 * and writes the chosen course's id into the hidden #course-id-input.
 */
(function () {
    const courses = window.COURSES_DATA || [];
    const searchInput = document.getElementById("course-search");
    const hiddenInput = document.getElementById("course-id-input");
    const hiddenCodeInput = document.getElementById("course-code-input"); // optional, not every page needs it
    const listEl = document.getElementById("course-picker-list");
    const selectedWrap = document.getElementById("course-picker-selected");
    const selectedText = document.getElementById("course-picker-selected-text");
    const clearBtn = document.getElementById("course-picker-clear");

    if (!searchInput) return; // not on this page

    function renderList(filtered) {
        listEl.innerHTML = "";
        if (filtered.length === 0) {
            listEl.innerHTML = '<div class="course-picker-empty">No matching courses</div>';
        } else {
            filtered.slice(0, 30).forEach((c) => {
                const item = document.createElement("div");
                item.className = "course-picker-item";
                item.innerHTML = `<strong>${c.course_code}</strong> — ${c.title}` +
                    (c.lecturer_name ? `<span class="course-picker-item-lecturer">${c.lecturer_name}</span>` : "");
                item.addEventListener("click", () => selectCourse(c));
                listEl.appendChild(item);
            });
        }
        listEl.style.display = "block";
    }

    function selectCourse(course) {
        hiddenInput.value = course.id;
        if (hiddenCodeInput) hiddenCodeInput.value = course.course_code;
        selectedText.textContent = `${course.course_code} — ${course.title}` +
            (course.lecturer_name ? ` (${course.lecturer_name})` : " (no lecturer assigned)");
        selectedWrap.style.display = "flex";
        searchInput.style.display = "none";
        listEl.style.display = "none";
        if (window.feather) feather.replace();
    }

    function clearSelection() {
        hiddenInput.value = "";
        selectedWrap.style.display = "none";
        searchInput.style.display = "block";
        searchInput.value = "";
        searchInput.focus();
    }

    searchInput.addEventListener("input", () => {
        const q = searchInput.value.trim().toLowerCase();
        if (!q) {
            listEl.style.display = "none";
            return;
        }
        const filtered = courses.filter((c) =>
            c.course_code.toLowerCase().includes(q) ||
            c.title.toLowerCase().includes(q) ||
            (c.lecturer_name || "").toLowerCase().includes(q)
        );
        renderList(filtered);
    });

    searchInput.addEventListener("focus", () => {
        if (searchInput.value.trim()) listEl.style.display = "block";
    });

    document.addEventListener("click", (e) => {
        if (!document.getElementById("course-picker").contains(e.target)) {
            listEl.style.display = "none";
        }
    });

    clearBtn.addEventListener("click", clearSelection);
})();
