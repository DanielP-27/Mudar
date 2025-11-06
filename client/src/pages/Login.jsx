import { MdOutlineLogin } from "react-icons/md";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/info-list.api";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      await login({ username, password });
      navigate("/menu");
    } catch (error) {
      setError(error.message || "Error en el inicio de sesión");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center  p-4 rounded-xl">
      <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl w-full max-w-md p-8 border border-white/20">
        <h1 className="text-4xl font-extrabold text-center text-white mb-4">
          Inicia Sesión
        </h1>
        <p className="text-center text-gray-200 mb-6 italic">
          Accede a tu cuenta para continuar
        </p>

        {error && (
          <p className="text-red-400 text-center font-semibold mb-4">{error}</p>
        )}

        <form className="flex flex-col gap-5" onSubmit={onSubmit}>
          {/* Usuario */}
          <div>
            <label className="block text-[#2C7EC9] font-semibold mb-1">
              Usuario
            </label>
            <input
              type="text"
              placeholder="Escribe tu usuario"
              className="w-full px-4 py-2 rounded-lg bg-white text-gray-900 shadow focus:outline-none focus:ring-2 focus:ring-green-500 transition"
              onChange={(e) => setUsername(e.target.value)}
              value={username}
            />
          </div>
          {/* Contraseña */}
          <div>
            <label className="block text-[#2C7EC9] font-semibold mb-1">
              Contraseña
            </label>
            <input
              type="password"
              placeholder="Escribe tu contraseña"
              className="w-full px-4 py-2 rounded-lg bg-white text-gray-900 shadow focus:outline-none focus:ring-2 focus:ring-green-500 transition"
              onChange={(e) => setPassword(e.target.value)}
              value={password}
            />
          </div>
          {/* Botón */}
          <button
            type="submit"
            className="flex items-center justify-center gap-2 bg-[#2C7EC9] hover:bg-[#76AEDE] text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300"
          >
            <MdOutlineLogin size={20} />
            Iniciar Sesión
          </button>
        </form>

        {/* Link extra */}
        <p className="text-center text-sm text-gray-300 mt-6">
          ¿No tienes cuenta?{" "}
          <span
            className="text-[#2C7EC9] hover:underline cursor-pointer"
            onClick={() => navigate("/register")}
          >
            Regístrate aquí
          </span>
        </p>
      </div>
    </div>
  );
}
