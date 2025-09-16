document.addEventListener("DOMContentLoaded", () => {
  const roadmap = document.getElementById("roadmap");
  const svg = document.getElementById("roadmap-lines");
  if (!roadmap || !svg) return;

  function drawLines() {
    const stages = Array.from(roadmap.querySelectorAll(".stage"));
    if (!stages.length) {
      svg.innerHTML = "";
      return;
    }

    svg.innerHTML = "";
    const svgRect = svg.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${svgRect.width} ${svgRect.height}`);
    svg.setAttribute("preserveAspectRatio", "none");

    // собираем центры кругов
    const centers = stages.map(el => {
      const c = el.querySelector(".circle").getBoundingClientRect();
      return {
        x: c.left + c.width / 2 - svgRect.left,
        y: c.top + c.height / 2 - svgRect.top
      };
    });

    // группировка по строкам
    const avgH = centers.reduce((s, p, _, arr) => s + p.y / arr.length, 0);
    const rowTolerance = 40; // допуск по Y
    const byY = centers.slice().sort((a, b) => a.y - b.y || a.x - b.x);
    const rows = [];
    byY.forEach(pt => {
      const last = rows[rows.length - 1];
      if (!last || Math.abs(pt.y - last[0].y) > rowTolerance) {
        rows.push([pt]);
      } else {
        last.push(pt);
      }
    });
    rows.forEach(r => r.sort((a, b) => a.x - b.x));

    // формируем змейку
    const orderedPoints = [];
    rows.forEach((row, i) => {
      const use = (i % 2 === 0) ? row : row.slice().reverse();
      orderedPoints.push(...use);
    });

    // строим path простыми линиями
    if (orderedPoints.length > 1) {
      let d = `M ${orderedPoints[0].x} ${orderedPoints[0].y}`;
      for (let i = 1; i < orderedPoints.length; i++) {
        d += ` L ${orderedPoints[i].x} ${orderedPoints[i].y}`;
      }
      drawPath(d);
    }
  }

  function drawPath(d) {
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "path");
    bg.setAttribute("d", d);
    bg.setAttribute("fill", "none");
    bg.setAttribute("stroke", "rgba(0,0,0,0.1)");
    bg.setAttribute("stroke-width", "12");
    bg.setAttribute("stroke-linecap", "round");
    svg.appendChild(bg);

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "#64748b");
    path.setAttribute("stroke-width", "4");
    path.setAttribute("stroke-linecap", "round");
    svg.appendChild(path);
  }

  setTimeout(drawLines, 50);

  let t;
  window.addEventListener("resize", () => {
    clearTimeout(t);
    t = setTimeout(drawLines, 150);
  });
});