// api/info-list.api.js
import axios from "axios";

const MudarApi = axios.create({
  baseURL: "http://127.0.0.1:8000",
  withCredentials: true,
});

MudarApi.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

//Registrar un usuario

export const register = async (userData) => {
  try {
    const response = await MudarApi.post("/register/", userData);
    return response.data;
  } catch (error) {
    console.error("Error en registro:", error.response?.data || error.message);
  }
};


// Procedimiento para login

export const login = async ({ username, password }) => {
  const response = await MudarApi.post("/login/", { username, password });
  localStorage.setItem("token", response.data.token);
  return response.data;
};

//Logout de un usuario

export const logout = async () => {
  try {
    const response = await MudarApi.post(
      "/logout/",
      {},
      {
        Authorization: `Token ${localStorage.getItem("token")}`,
      }
    );
    localStorage.removeItem("token");
    return response.data;
  } catch (error) {
    console.error("Error en registro:", error.response?.data || error.message);
  }
};