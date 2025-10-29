document.addEventListener("DOMContentLoaded", () => {
    const popup = document.getElementById("stage-popup");
    if (!popup) return;

    const closeBtn = popup.querySelector(".close-popup");
    if (!closeBtn) return;

    closeBtn.addEventListener("click", () => {
        // плавное исчезновение
        popup.classList.add("animate-fade-out");

        popup.addEventListener("animationend", () => {
            popup.style.display = "none";
        }, { once: true });

        fetch("/mark-stage-popup-shown/", {
            method: "POST",
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "XMLHttpRequest"
            }
        })
        .then(r => r.json())
        .then(data => console.log("Popup status updated:", data))
        .catch(err => console.error("Error:", err));
    });
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
