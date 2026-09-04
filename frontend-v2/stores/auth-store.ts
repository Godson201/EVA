"use client";

import { create } from "zustand";
import type { User } from "@/types/api";

type AuthState = {
  accessToken: string | null;
  user: User | null;
  hydrated: boolean;
  setSession: (accessToken: string, user: User) => void;
  clear: () => void;
  setHydrated: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  hydrated: false,
  setSession: (accessToken, user) => set({ accessToken, user, hydrated: true }),
  clear: () => set({ accessToken: null, user: null, hydrated: true }),
  setHydrated: () => set({ hydrated: true }),
}));
