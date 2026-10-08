import { createContext, useCallback, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { api, setToken, token, setAuthLost, Rec } from "./lib";

type Toast = { id: number; msg: string; kind: "ok" | "err" };
interface Ctx {
  user: Rec | null; login: (u: string, p: string) => Promise<void>; logout: () => Promise<void>;
  cases: Rec[]; refreshCases: () => Promise<void>; caseId: string; setCaseId: (id: string) => void; activeCase?: Rec;
  toast: (msg: string, kind?: "ok" | "err") => void; toasts: Toast[]; ready: boolean; canWrite: boolean;
  theme: string; toggleTheme: () => void;
}
const C = createContext<Ctx>(null as any);
export const useApp = () => useContext(C);

export function Provider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Rec | null>(null);
  const [ready, setReady] = useState(false);
  const [cases, setCases] = useState<Rec[]>([]);
  const [caseId, setCaseIdS] = useState(localStorage.getItem("ob_case") || "");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [theme, setTheme] = useState(localStorage.getItem("ob_theme") || "dark");
  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); localStorage.setItem("ob_theme", theme); }, [theme]);
  const toast = useCallback((msg: string, kind: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random(); setToasts((t) => [...t, { id, msg, kind }]); setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "err" ? 7000 : 3500);
  }, []);
  const refreshCases = useCallback(async () => { try { const r = await api("/cases?size=200"); setCases(r.items); } catch { /* handled globally */ } }, []);
  useEffect(() => {
    setAuthLost(() => { setUser(null); setCases([]); });
    (async () => { if (token()) { try { setUser(await api("/auth/me")); } catch { setToken(null); } } setReady(true); })();
  }, []);
  useEffect(() => { if (user) refreshCases(); }, [user, refreshCases]);
  const setCaseId = (id: string) => { setCaseIdS(id); localStorage.setItem("ob_case", id); };
  const value = useMemo<Ctx>(() => ({
    user, ready, cases, refreshCases, caseId, setCaseId, toast, toasts, theme, toggleTheme: () => setTheme(theme === "dark" ? "light" : "dark"),
    activeCase: cases.find((c) => c.id === caseId), canWrite: !!user && user.role !== "viewer",
    login: async (u, p) => { const r = await api("/auth/login", { body: { username: u, password: p } }); setToken(r.token); setUser(r.user); },
    logout: async () => { try { await api("/auth/logout", { method: "POST" }); } catch { /* ignore */ } setToken(null); setUser(null); setCases([]); },
  }), [user, ready, cases, caseId, toasts, theme, toast, refreshCases]);
  return <C.Provider value={value}>{children}</C.Provider>;
}
