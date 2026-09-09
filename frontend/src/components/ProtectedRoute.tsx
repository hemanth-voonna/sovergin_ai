import { Navigate, Outlet, useLocation } from "react-router-dom";
import { getToken, getUser } from "../api";

export default function ProtectedRoute() {
  const location = useLocation();
  const token = getToken();
  const user = getUser();

  if (!token || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
