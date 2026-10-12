import CourseCard from "./CourseCard";
import type { Course } from "../lib/types/components";
import "./CourseList.css";

export const CourseList = ({ courses }: { courses: Course[] }) => {
  if (!courses.length) {
    return <div className="courses-empty">Пока нет доступных курсов. Обратитесь к администратору, чтобы получить доступ к обучению.</div>;
  }
  return <div className="courses-grid">{courses.map((course) => <CourseCard key={course.id} course={course} />)}</div>;
};
