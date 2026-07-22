// CourseList.tsx (оставляем как есть, но добавляем комментарии для ясности)
import CourseCard from "./CourseCard";
import type { Course } from "../lib/types/components";
import { useRef } from "react";

interface CourseListProps {
  courses: Course[];
}

export const CourseList = ({ courses }: CourseListProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  if (!courses.length) {
    return <p>Нет доступных курсов</p>;
  }

  const scrollLeft = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: -300, behavior: "smooth" });
    }
  };

  const scrollRight = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: 300, behavior: "smooth" });
    }
  };

  return (
    <div style={{ position: "relative", width: "1200px", marginTop: '5%' }}>
      {courses.length > 3 && (
        <button
          onClick={scrollLeft}
          style={{
            position: "absolute",
            left: "-40px",
            top: "50%",
            transform: "translateY(-50%)",
            background: "rgba(0,0,0,0.5)",
            color: "white",
            border: "none",
            borderRadius: "50%",
            width: "40px",
            height: "40px",
            cursor: "pointer",
            zIndex: 10,
          }}
        >
          ←
        </button>
      )}
      <div
        ref={scrollRef}
        style={{
          display: "grid",
          gridAutoFlow: "column",
          gridAutoColumns: "minmax(300px, 300px)",
          gap: 60,
          overflowX: "auto",
          scrollBehavior: "smooth",
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        {courses.map((course) => (
          <CourseCard key={course.id} course={course} />
        ))}
      </div>
      {courses.length > 3 && (
        <button
          onClick={scrollRight}
          style={{
            position: "absolute",
            right: "-40px",
            top: "50%",
            transform: "translateY(-50%)",
            background: "rgba(0,0,0,0.5)",
            color: "white",
            border: "none",
            borderRadius: "50%",
            width: "40px",
            height: "40px",
            cursor: "pointer",
            zIndex: 10,
          }}
        >
          →
        </button>
      )}
    </div>
  );
};