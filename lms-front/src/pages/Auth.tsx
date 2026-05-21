import { useEffect, useState } from "react";
import "./Auth.css";
import { Alert, MenuItem, TextField } from "@mui/material";
import { RegistateUser, LoginUser } from "../lib/auth";
import { useNavigate } from "react-router-dom";

const Auth = () => {
  const [isRegister, setIsRegister] = useState(false);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [department, setDepartment] = useState('');
  const [needsDepartment, setNeedsDepartment] = useState(false);
  const [alertShown, setAlertShown] = useState(false);
  const [alertText, setAlertText] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    if (alertShown) {
      const timer = setTimeout(() => setAlertShown(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [alertShown]);

  async function onLoginClick() {
    if (login && password) {
      try {
        const result = await LoginUser(login, password, department);
        if (result.user) {
          localStorage.setItem("user", result.user.id.toString()); // Сохраняем user.id как "user"
          localStorage.setItem("username", result.user.username);
          localStorage.setItem("department", result.user.department);
          localStorage.setItem("departments", JSON.stringify(result.user.departments || []));
          navigate("/dashboard", { replace: true });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Произошла ошибка";
        setAlertText(message);
        setAlertShown(true);
        if (message.includes("отдел")) {
          setNeedsDepartment(true);
        }
      }
    } else {
      setAlertText("Заполните логин и пароль!");
      setAlertShown(true);
    }
  }

  async function onRegisterClick() {
    if (login && password && department) {
      try {
        const result = await RegistateUser(login, password, department);
        if (result.user) { // Исправлено: проверяем result.user, а не result.department
          localStorage.setItem("user", result.user.id.toString()); // Сохраняем user.id как "user"
          localStorage.setItem("username", result.user.username);
          localStorage.setItem("department", result.user.department);
          localStorage.setItem("departments", JSON.stringify(result.user.departments || []));
          navigate("/dashboard", { replace: true });
        }
      } catch (error) {
        if (error instanceof Error) {
          setAlertText(error.message);
        } else {
          setAlertText("Неизвестная ошибка");
        }
        setAlertShown(true);
      }
    } else {
      setAlertText("Заполните логин, отдел и пароль!");
      setAlertShown(true);
    }
  }

  return (
    <div className="auth">
      <div className={`auth-card`}>
        {/* ВХОД */}
        <div className="form login">
          <h2>Вход</h2>
          <input value={login} onChange={(e) => setLogin(e.target.value)} type="text" placeholder="Логин" />
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Пароль" />
          <div className={`department-wrapper ${isRegister || needsDepartment ? "open" : ""}`}>
            <TextField
              variant="filled"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              select
              sx={{
                color: 'darkgray',
                backgroundColor: 'rgb(30, 30, 30);',
                display: "flex",
                zIndex: '1',
                "& .MuiFormLabel-root": {
                  color: 'darkgray'
                },
                "& .MuiSelect-select": {
                  color: 'white',
                  textAlign: 'start'
                }
              }}
              label="Отдел"
            >
              <MenuItem value="sales">Продажи</MenuItem>
              <MenuItem value="marketing">Маркетинг</MenuItem>
              <MenuItem value="moderation">Модерация</MenuItem>
              <MenuItem value="firstline">Первая линия</MenuItem>
              <MenuItem value="support">Отдел сопровождения</MenuItem>
              <MenuItem value="law">Юридический</MenuItem>
            </TextField>
          </div>
          {!isRegister && <button onClick={onLoginClick}>Войти</button>}
          {isRegister && <button onClick={onRegisterClick}>Зарегистрироваться</button>}
        </div>
        <div className="alert-container">
          {alertShown && (
            <Alert severity="error" className="custom-alert">
              {alertText}
            </Alert>
          )}
        </div>
      </div>
      {/* ПЕРЕКЛЮЧАТЕЛЬ */}
      <p className="switch">
        {isRegister ? "Уже есть аккаунт?" : "Нет аккаунта?"}
        <span onClick={() => {
          setIsRegister(!isRegister);
          setNeedsDepartment(false);
        }}>
          {isRegister ? " Войти" : " Зарегистрироваться"}
        </span>
      </p>
    </div>
  );
};

export default Auth;
