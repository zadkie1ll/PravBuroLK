document.addEventListener("DOMContentLoaded", () => {
  const stages = document.querySelectorAll("#roadmap .stage");
  const svg = document.getElementById("roadmap-lines");

  if (!stages.length || !svg) return;

  const drawLines = () => {
    svg.innerHTML = ""; // очистка
    const container = svg.getBoundingClientRect();
    const isMobile = window.innerWidth < 640; // sm breakpoint

    if (isMobile) {
      // мобильная версия (прямая)
      for (let i = 0; i < stages.length - 1; i++) {
        const start = stages[i].querySelector(".circle").getBoundingClientRect();
        const end = stages[i + 1].querySelector(".circle").getBoundingClientRect();

        const x1 = start.left + start.width / 2 - container.left;
        const y1 = start.top + start.height / 2 - container.top;
        const x2 = end.left + end.width / 2 - container.left;
        const y2 = end.top + end.height / 2 - container.top;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", x1);
        line.setAttribute("y1", y1);
        line.setAttribute("x2", x2);
        line.setAttribute("y2", y2);
        line.setAttribute("stroke", "#9ca3af");
        line.setAttribute("stroke-width", "3");

        svg.appendChild(line);
      }
      return;
    }

    // десктопный зигзаг
    const stagesArr = Array.from(stages);
    const lastStage = stagesArr.find((s) => s.classList.contains("last-stage"));

    // исключаем последний из зигзага
    const normalStages = lastStage
      ? stagesArr.filter((s) => !s.classList.contains("last-stage"))
      : stagesArr;

    const cols = 4; // твоя md:grid-cols-4
    let direction = "ltr";

    for (let rowStart = 0; rowStart < normalStages.length; rowStart += cols) {
      const rowStages = normalStages.slice(rowStart, rowStart + cols);

      if (direction === "rtl") {
        rowStages.reverse();
      }

      for (let i = 0; i < rowStages.length - 1; i++) {
        const start = rowStages[i].querySelector(".circle").getBoundingClientRect();
        const end = rowStages[i + 1].querySelector(".circle").getBoundingClientRect();

        const x1 = start.left + start.width / 2 - container.left;
        const y1 = start.top + start.height / 2 - container.top;
        const x2 = end.left + end.width / 2 - container.left;
        const y2 = end.top + end.height / 2 - container.top;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", x1);
        line.setAttribute("y1", y1);
        line.setAttribute("x2", x2);
        line.setAttribute("y2", y2);
        line.setAttribute("stroke", "#9ca3af");
        line.setAttribute("stroke-width", "3");

        svg.appendChild(line);
      }

      direction = direction === "ltr" ? "rtl" : "ltr";
    }

    // соединяем последний элемент только с предпоследним
    if (lastStage) {
      const prev = normalStages[normalStages.length - 1].querySelector(".circle").getBoundingClientRect();
      const end = lastStage.querySelector(".circle").getBoundingClientRect();

      const x1 = prev.left + prev.width / 2 - container.left;
      const y1 = prev.top + prev.height / 2 - container.top;
      const x2 = end.left + end.width / 2 - container.left;
      const y2 = end.top + end.height / 2 - container.top;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      line.setAttribute("stroke", "#9ca3af");
      line.setAttribute("stroke-width", "3");

      svg.appendChild(line);
    }
  };

  drawLines();
  window.addEventListener("resize", drawLines);
});