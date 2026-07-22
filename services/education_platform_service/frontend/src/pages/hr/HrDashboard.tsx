import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Button,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Checkbox,
  FormControlLabel,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  CircularProgress,
  Alert,
  Stack,
  Divider,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import { useStaffGuard } from "../../lib/useStaffGuard";
import {
  loadDashboard,
  listDepartments,
  createCourse,
  updateCourse,
  createModule,
  updateModule,
  createMaterial,
  deleteMaterial,
  type HrCourseTree,
  type HrModule,
  type HrDepartment,
} from "../../lib/hrApi";

function CourseDialog({
  open,
  onClose,
  onSaved,
  departments,
  course,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  departments: HrDepartment[];
  course: HrCourseTree | null;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(course?.name || "");
    setDescription(course?.description || "");
    setImageUrl(course?.image_url || "");
    setPhotoUrl(course?.photo_url || "");
    setIsActive(course?.is_active ?? true);
    setSelectedDepts(course?.department_codes || []);
    setError(null);
  }, [open, course]);

  const toggleDept = (code: string) => {
    setSelectedDepts((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name,
        description,
        image_url: imageUrl,
        photo_url: photoUrl,
        is_active: isActive,
        department_codes: selectedDepts,
      };
      if (course) await updateCourse(course.id, payload);
      else await createCourse(payload);
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{course ? "Редактировать курс" : "Новый курс"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Название" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
          <TextField label="Описание" value={description} onChange={(e) => setDescription(e.target.value)} multiline rows={3} fullWidth />
          <TextField label="image_url" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} fullWidth />
          <TextField label="photo_url" value={photoUrl} onChange={(e) => setPhotoUrl(e.target.value)} fullWidth />
          <Box>
            <Typography variant="subtitle2">Отделы</Typography>
            {departments.map((d) => (
              <FormControlLabel
                key={d.code}
                control={<Checkbox checked={selectedDepts.includes(d.code)} onChange={() => toggleDept(d.code)} />}
                label={d.name}
              />
            ))}
          </Box>
          <FormControlLabel control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />} label="Активен" />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || !name}>
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ModuleDialog({
  open,
  onClose,
  onSaved,
  courseId,
  module,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  courseId: number;
  module: HrModule | null;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [order, setOrder] = useState(1);
  const [isActive, setIsActive] = useState(true);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(module?.name || "");
    setDescription(module?.description || "");
    setVideoUrl(module?.video_url || "");
    setOrder(module?.order ?? 1);
    setIsActive(module?.is_active ?? true);
    setVideoFile(null);
    setError(null);
  }, [open, module]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = { course_id: courseId, name, description, video_url: videoUrl, order, is_active: isActive, private_video: videoFile };
      if (module) await updateModule(module.id, payload);
      else await createModule(payload);
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{module ? "Редактировать модуль" : "Новый модуль"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Название" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
          <TextField label="Описание" value={description} onChange={(e) => setDescription(e.target.value)} multiline rows={3} fullWidth />
          <TextField label="video_url (если видео внешнее)" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} fullWidth />
          <Button variant="outlined" component="label">
            {videoFile ? videoFile.name : "Загрузить приватное видео"}
            <input type="file" accept="video/*" hidden onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
          </Button>
          <TextField label="Порядок" type="number" value={order} onChange={(e) => setOrder(Number(e.target.value))} fullWidth />
          <FormControlLabel control={<Checkbox checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />} label="Активен" />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || !name}>
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MaterialDialog({
  open,
  onClose,
  onSaved,
  moduleId,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  moduleId: number;
}) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setFile(null);
    setError(null);
  }, [open]);

  const handleSave = async () => {
    if (!file) {
      setError("Выберите файл");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createMaterial(moduleId, { title, file });
      onSaved();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Новый материал</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Название" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <Button variant="outlined" component="label">
            {file ? file.name : "Выбрать файл"}
            <input type="file" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </Button>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Отмена</Button>
        <Button variant="contained" onClick={handleSave} disabled={saving || !title}>
          Сохранить
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function HrDashboard() {
  const ready = useStaffGuard();
  const navigate = useNavigate();
  const [courses, setCourses] = useState<HrCourseTree[]>([]);
  const [departments, setDepartments] = useState<HrDepartment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [courseDialogOpen, setCourseDialogOpen] = useState(false);
  const [editingCourse, setEditingCourse] = useState<HrCourseTree | null>(null);

  const [moduleDialogOpen, setModuleDialogOpen] = useState(false);
  const [moduleCourseId, setModuleCourseId] = useState<number | null>(null);
  const [editingModule, setEditingModule] = useState<HrModule | null>(null);

  const [materialDialogOpen, setMaterialDialogOpen] = useState(false);
  const [materialModuleId, setMaterialModuleId] = useState<number | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const [tree, depts] = await Promise.all([loadDashboard(), listDepartments()]);
      setCourses(tree);
      setDepartments(depts);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ready) refresh();
  }, [ready]);

  if (!ready) return null;
  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: "auto" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          HR-админка
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" onClick={() => navigate("/hr/trainees")}>
            Стажёры
          </Button>
          <Button
            variant="contained"
            onClick={() => {
              setEditingCourse(null);
              setCourseDialogOpen(true);
            }}
          >
            + Курс
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {courses.map((course) => (
        <Accordion key={course.id} sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%" }}>
              <Typography sx={{ flexGrow: 1 }}>{course.name}</Typography>
              {!course.is_active && <Chip label="неактивен" size="small" color="default" />}
              {course.department_codes.map((code) => (
                <Chip key={code} label={code} size="small" />
              ))}
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingCourse(course);
                  setCourseDialogOpen(true);
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Stack>
          </AccordionSummary>
          <AccordionDetails>
            {course.modules.map((module) => (
              <Paper key={module.id} variant="outlined" sx={{ p: 2, mb: 1 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography fontWeight="bold">
                    {module.order}. {module.name} {!module.is_active && <Chip label="неактивен" size="small" sx={{ ml: 1 }} />}
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => navigate(`/hr/module/${module.id}/test`)}>
                      Тест {module.test ? `(${module.test.questions_count} вопр.)` : ""}
                    </Button>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setEditingModule(module);
                        setModuleCourseId(course.id);
                        setModuleDialogOpen(true);
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                </Stack>
                <Divider sx={{ my: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  Материалы:
                </Typography>
                {module.materials.map((material) => (
                  <Stack key={material.id} direction="row" alignItems="center" spacing={1}>
                    <Typography variant="body2" sx={{ flexGrow: 1 }}>
                      {material.title}
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={async () => {
                        await deleteMaterial(material.id);
                        refresh();
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                ))}
                <Button
                  size="small"
                  sx={{ mt: 1 }}
                  onClick={() => {
                    setMaterialModuleId(module.id);
                    setMaterialDialogOpen(true);
                  }}
                >
                  + Материал
                </Button>
              </Paper>
            ))}
            <Button
              onClick={() => {
                setEditingModule(null);
                setModuleCourseId(course.id);
                setModuleDialogOpen(true);
              }}
            >
              + Модуль
            </Button>
          </AccordionDetails>
        </Accordion>
      ))}

      <CourseDialog
        open={courseDialogOpen}
        onClose={() => setCourseDialogOpen(false)}
        onSaved={refresh}
        departments={departments}
        course={editingCourse}
      />
      {moduleCourseId !== null && (
        <ModuleDialog
          open={moduleDialogOpen}
          onClose={() => setModuleDialogOpen(false)}
          onSaved={refresh}
          courseId={moduleCourseId}
          module={editingModule}
        />
      )}
      {materialModuleId !== null && (
        <MaterialDialog
          open={materialDialogOpen}
          onClose={() => setMaterialDialogOpen(false)}
          onSaved={refresh}
          moduleId={materialModuleId}
        />
      )}
    </Box>
  );
}
