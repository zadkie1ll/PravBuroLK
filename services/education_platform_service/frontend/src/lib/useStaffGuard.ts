import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GetInfoAboutMe } from "./auth";

export function useStaffGuard() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const cached = localStorage.getItem("is_staff");
        if (cached !== null) {
          if (cached !== "true") {
            navigate("/dashboard", { replace: true });
            return;
          }
          if (!cancelled) setReady(true);
        }
        const me = await GetInfoAboutMe();
        localStorage.setItem("is_staff", String(me.user.is_staff));
        if (!me.user.is_staff) {
          navigate("/dashboard", { replace: true });
          return;
        }
        if (!cancelled) setReady(true);
      } catch {
        navigate("/auth", { replace: true });
      }
    };
    check();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return ready;
}
