"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const { hydrated, setSession, setHydrated } = useAuthStore();
  useEffect(() => {
    api.refresh().then((session) => setSession(session.access_token, session.user)).catch(setHydrated);
  }, [setHydrated, setSession]);
  if (!hydrated) return <div className="boot"><div className="eva-mark">E</div><p>Preparing EVA</p></div>;
  return children;
}
