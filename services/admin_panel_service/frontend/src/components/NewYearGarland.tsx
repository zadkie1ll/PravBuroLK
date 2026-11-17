import { useId, useState } from "react";
import "./NewYearGarland.css";

const STORAGE_KEY = "pravburo:garland-enabled";

export function NewYearGarland() {
  const patternId = useId().replace(/:/g, "");
  const [enabled, setEnabled] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== "false";
    } catch {
      return true;
    }
  });
  const [pulling, setPulling] = useState(false);

  function toggle() {
    const next = !enabled;
    setEnabled(next);
    try {
      localStorage.setItem(STORAGE_KEY, String(next));
    } catch {
      // The switch still works when browser storage is unavailable.
    }
  }

  return (
    <div className="new-year-garland" data-enabled={enabled}>
      <svg className="new-year-garland__lights" width="100%" height="48" aria-hidden="true">
        <defs>
          <pattern id={patternId} width="240" height="48" patternUnits="userSpaceOnUse">
            <path className="new-year-garland__wire" d="M-120 4 Q0 39 120 4 Q240 39 360 4" />
            {[
              { x: 30, y: 17, color: "rose", angle: 12 },
              { x: 90, y: 17, color: "gold", angle: -12 },
              { x: 150, y: 17, color: "mint", angle: 12 },
              { x: 210, y: 17, color: "ice", angle: -12 },
            ].map(({ x, y, color, angle }, index) => (
              <g key={color} transform={`translate(${x} ${y}) rotate(${angle})`}>
                <path className="new-year-garland__socket" d="M-3-2h6v6h-6z" />
                <g className={`new-year-garland__bulb new-year-garland__bulb--${color}`}>
                  <ellipse className={`new-year-garland__halo new-year-garland__halo--${index}`} cy="10" rx="17" ry="17" />
                  <path className="new-year-garland__glass" d="M-3 3C-5 6-6 10-4 14Q0 20 4 14C6 10 5 6 3 3Z" />
                  <path className="new-year-garland__shine" d="M-1 6Q-3 9-2 12" />
                </g>
              </g>
            ))}
          </pattern>
        </defs>
        <rect width="100%" height="48" fill={`url(#${patternId})`} />
      </svg>

      <button
        type="button"
        className="new-year-garland__switch"
        data-pulling={pulling}
        aria-label="Новогодняя гирлянда"
        aria-pressed={enabled}
        onClick={toggle}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          setPulling(true);
        }}
        onPointerUp={() => setPulling(false)}
        onPointerCancel={() => setPulling(false)}
        onLostPointerCapture={() => setPulling(false)}
        onKeyDown={(event) => {
          if (event.key === " " || event.key === "Enter") setPulling(true);
        }}
        onKeyUp={() => setPulling(false)}
        onBlur={() => setPulling(false)}
      >
        <span className="new-year-garland__cord" aria-hidden="true" />
        <span className="new-year-garland__handle" aria-hidden="true">
          <span />
        </span>
        <span className="new-year-garland__tooltip" aria-hidden="true">
          {enabled ? "Погасить огоньки" : "Зажечь огоньки"}
        </span>
      </button>
    </div>
  );
}
