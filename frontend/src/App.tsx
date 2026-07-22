import "./App.css";

import { DashboardLayout } from "./layouts/DashboardLayout";
import { OperationsPage } from "./pages/OperationsPage";

function App() {
  return (
    <DashboardLayout>
      <OperationsPage />
    </DashboardLayout>
  );
}

export default App;