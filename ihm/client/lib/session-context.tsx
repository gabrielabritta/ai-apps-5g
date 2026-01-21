"use client";

import { createContext, useContext, useRef, ReactNode } from "react";

interface SessionContextType {
  sessionId: string;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  // Generate a unique session ID once per provider instance
  const sessionIdRef = useRef<string>(
    `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  );

  return (
    <SessionContext.Provider value={{ sessionId: sessionIdRef.current }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionId() {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error("useSessionId must be used within a SessionProvider");
  }
  return context.sessionId;
}
