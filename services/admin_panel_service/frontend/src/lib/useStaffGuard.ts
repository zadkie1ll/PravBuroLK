import { useEffect, useState } from "react";
import { api } from "../api/client";

export function useStaffGuard() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api.me().then(({ user }) => {
      if (!cancelled) setReady(user.is_staff && ["admin", "director"].includes(user.role));
    }).catch(() => { if (!cancelled) setReady(false); });
    return () => { cancelled = true; };
  }, []);
  return ready;
}
