import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, setToken } from "../api/client";

// Принимает переход из бот-админки (bot_pravburo, GET /api/auth/sso-to-lk) — та уже
// аутентифицировала юзера своей сессией и передаёт сюда короткоживущий (2 мин) JWT,
// подписанный общим SSO_JWT_SECRET. Сохранять его напрямую как access_token нельзя —
// он без role/is_staff и живёт 2 минуты, поэтому меняем его на POST /auth/sso-exchange
// на полноценную здешнюю сессию (обычный access_token + refresh-кука на 7 дней).
export function SsoPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      navigate("/login?sso_failed=1", { replace: true });
      return;
    }
    api
      .ssoExchange(token)
      .then((res) => {
        setToken(res.access_token);
        navigate("/admin-panel", { replace: true });
      })
      .catch(() => navigate("/login?sso_failed=1", { replace: true }));
  }, [navigate, searchParams]);

  return null;
}
