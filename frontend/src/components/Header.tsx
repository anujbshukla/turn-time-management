import type { ReactNode } from "react";

interface HeaderProps {
  children?: ReactNode;
  notification?: ReactNode;
}

export function Header({ children, notification }: HeaderProps) {
  return (
    <header className="top-header compact-operations-header">
      {children && (
        <div className="top-header-controls">
          {children}
        </div>
      )}

      {notification && (
        <div className="top-header-notification-row">
          {notification}
        </div>
      )}
    </header>
  );
}
