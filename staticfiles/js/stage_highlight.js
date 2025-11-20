document.addEventListener("DOMContentLoaded", () => {
  const containers = document.querySelectorAll("[data-current-stage]");
  if (!containers.length) return;

  // --- Анимации свечения ---
  const style = document.createElement("style");
  style.textContent = `
    @keyframes pulse-glow {
      0%, 100% { box-shadow: 0 0 18px rgba(59,130,246,0.7), 0 0 35px rgba(59,130,246,0.4); }
      50% { box-shadow: 0 0 25px rgba(59,130,246,1), 0 0 50px rgba(59,130,246,0.7); }
    }
    @keyframes pulse-glow-green {
      0%, 100% { box-shadow: 0 0 20px rgba(34,197,94,0.8), 0 0 40px rgba(34,197,94,0.5); }
      50% { box-shadow: 0 0 28px rgba(22,163,74,1), 0 0 55px rgba(22,163,74,0.7); }
    }
  `;
  document.head.appendChild(style);

  containers.forEach(container => {
    const current = parseInt(container.dataset.currentStage, 10);
    const elements = container.querySelectorAll("[data-stage]");

    elements.forEach(el => {
      const order = parseInt(el.dataset.stage, 10);

      const svg = el.querySelector("svg");
      const circle = svg ? svg.querySelector("circle") : null;
      const pathEl = svg ? svg.querySelector("path") : null;
      const triangles = el.querySelectorAll(".triangle");

      const isCircle = el.classList.contains("rounded-full") || !!circle;
      const isLine = el.classList.contains("border-t-[3px]") || el.classList.contains("outline");

      // --- Сброс оформления ---
      el.style.background = "";
      el.style.borderColor = "";
      el.style.outlineColor = "";
      el.style.boxShadow = "";
      el.style.animation = "";
      el.style.color = "#365C80"; // сброс цвета текста по умолчанию

      if (pathEl) pathEl.setAttribute("fill", "#365C80");
      if (circle) {
        circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", "#365C80");
      }
      triangles.forEach(t => (t.style.borderTopColor = "#365C80"));

      let color = null;

      // ---- ПРОЙДЕННЫЕ ----
      if (order < current) {
        const gradient = "linear-gradient(135deg, #60a5fa, #3b82f6)";
        color = "#3b82f6";

        if (isCircle) {
          if (circle) {
            circle.setAttribute("fill", "#60a5fa");
            circle.setAttribute("stroke", "#3b82f6");
          } else {
            el.style.background = gradient;
            el.style.borderColor = "#3b82f6";
          }
        } else if (isLine) {
          if (el.classList.contains("outline"))
            el.style.outlineColor = "#3b82f6";
          else
            el.style.borderImage = "linear-gradient(to right, #60a5fa, #3b82f6) 1";
        } else if (pathEl) {
          pathEl.setAttribute("fill", "#3b82f6");
        }

        // 🎯 красим стрелки
        triangles.forEach(t => (t.style.borderTopColor = color));

        // 🎨 делаем текст белым
        el.style.color = "white";
      }

      // ---- ТЕКУЩАЯ ----
      else if (order === current) {
        if (isCircle) {
          if (circle) {
            color = order === 8 ? "#22c55e" : "#3b82f6";
            circle.setAttribute("fill", color);
            circle.setAttribute("stroke", order === 8 ? "#16a34a" : "#1d4ed8");
          } else {
            if (order === 8) {
              color = "#22c55e";
              el.style.background = "linear-gradient(135deg, #16a34a, #22c55e)";
              el.style.borderColor = "#16a34a";
              el.style.animation = "pulse-glow-green 2s infinite";
            } else {
              color = "#3b82f6";
              el.style.background = "linear-gradient(135deg, #3b82f6, #1d4ed8)";
              el.style.borderColor = "#1d4ed8";
              el.style.animation = "pulse-glow 2s infinite";
            }
          }

          if (!el.classList.contains("rounded-full")) {
            el.style.animation =
              order === 8 ? "pulse-glow-green 2s infinite" : "pulse-glow 2s infinite";
          }
        } else if (isLine) {
          color = order === 8 ? "#16a34a" : "#1d4ed8";
          if (el.classList.contains("outline")) el.style.outlineColor = color;
          else el.style.borderImage = `linear-gradient(to right, #60a5fa, ${color}) 1`;
        } else if (pathEl) {
          color = "#3b82f6";
          pathEl.setAttribute("fill", color);
        }

        // 🎯 красим стрелки для текущего этапа
        triangles.forEach(t => {
          t.style.borderTopColor = "#3b82f6";
          t.style.animation =
            order === 8 ? "pulse-glow-green 2s infinite" : "pulse-glow 2s infinite";
        });

        // 🎨 делаем текст белым
        el.style.color = "white";
      }
    });
  });
});