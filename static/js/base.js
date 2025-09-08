// === Открытие сайдбара ===
function openSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");
    if (!sidebar || !overlay) return;

    sidebar.classList.remove("translate-x-full");
    sidebar.classList.add("translate-x-0");
    overlay.classList.remove("hidden");
}

// === Закрытие сайдбара ===
function closeSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");
    if (!sidebar || !overlay) return;

    sidebar.classList.remove("translate-x-0");
    sidebar.classList.add("translate-x-full");
    overlay.classList.add("hidden");
}

// === Инициализация ===
function initSidebar() {
    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("menu-toggle");
    const closeBtn = document.getElementById("close-sidebar");
    const overlay = document.getElementById("overlay");

    if (!sidebar) return;

    // Кнопка открытия
    if (toggleBtn) toggleBtn.addEventListener("click", openSidebar);

    // Кнопка закрытия
    if (closeBtn) closeBtn.addEventListener("click", closeSidebar);

    // Клик по overlay
    if (overlay) overlay.addEventListener("click", closeSidebar);

    // Клик по ссылкам в сайдбаре
    sidebar.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", closeSidebar);
    });
}

document.addEventListener("DOMContentLoaded", initSidebar);