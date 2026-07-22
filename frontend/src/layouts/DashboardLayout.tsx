import type {
  ReactNode,
} from "react";

import { Sidebar } from "../components/Sidebar";

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({
  children,
}: DashboardLayoutProps) {
  return (
    <div className="app-layout">
      <Sidebar />

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}