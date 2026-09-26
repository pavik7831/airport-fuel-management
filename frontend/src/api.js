import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  withCredentials: true,
});
api.interceptors.request.use((config) => {
  const csrf = document.cookie
    .split("; ")
    .find((item) => item.startsWith("afm_csrf="))
    ?.split("=")
    .slice(1)
    .join("=");
  if (
    csrf &&
    !["get", "head", "options"].includes(config.method?.toLowerCase())
  )
    config.headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  return config;
});
api.interceptors.response.use(
  (value) => value,
  (error) => {
    if (
      error.response?.status === 401 &&
      !location.pathname.startsWith("/login")
    )
      window.dispatchEvent(new Event("afm:unauthorized"));
    return Promise.reject(error);
  },
);

export const errorMessage = (error) =>
  error.response?.data?.detail || error.message || "Request failed";
