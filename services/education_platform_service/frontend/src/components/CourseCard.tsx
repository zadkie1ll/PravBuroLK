import { LinearProgress, Button } from "@mui/material";
import type { Course } from "../lib/types/components";
import "./CourseCard.css";
import { useNavigate } from "react-router-dom";

interface CourseCardProps {
  course: Course;
}

const CourseCard = ({ course }: CourseCardProps) => {
  const completed = course.completed_modules ?? 0;
  const navigate = useNavigate()
  const percent = course.modules_count > 0 ? Math.round(
    (completed / course.modules_count) * 100
  ) : 0;
  const url = `/course/${course.id}`
  return (
    <div className="course-card">
      <div className="course-image-wrapper">
        <img src={course.image_url} alt={course.name} />
      </div>

      <div className="course-body">
        <h3>{course.name}</h3>
        <p>{course.description}</p>

        <div className="course-progress">
          <div className="progress-label">
            <span>
              {completed} / {course.modules_count} модулей
            </span>
            <span>{percent}%</span>
          </div>

          <LinearProgress
            variant="determinate"
            value={percent}
            sx={{ height: 8, borderRadius: 4 }}
          />
        </div>

        <Button
          variant="contained"
          fullWidth
          sx={{ marginTop: 2 }}
          onClick={() => navigate(url, {replace: true})}
        >
          {percent === 100 ? "Повторить" : "Продолжить"}
        </Button>
      </div>
    </div>
  );
};

export default CourseCard;
