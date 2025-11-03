import { IoSaveSharp } from "react-icons/io5";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { register } from "../api/info-list.api";
import { toast } from "react-hot-toast";


export function Register() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");

    try {
      await toast.promise(
        register({ username, password }),
        {
          loading: "Registrando usuario...",
          success: "Usuario registrado correctamente",
          error: "Error al registrar usuario",
        },
        {
          position: "bottom-right",
          style: {
            background: "#101010",
            color: "#14d5be",
          },
        }
      );

      navigate("/"); // solo si todo salió bien
    } catch (error) {
      setError(error.message || "Error al guardar información");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center  p-4 rounded-xl">
      <div className="bg-white/10 backdrop-blur-lg rounded-xl shadow-xl w-full max-w-md p-8 border border-white/20">
        <h1 className="text-4xl font-extrabold text-center text-white mb-4">
          Regístrate
        </h1>
        <p className="text-white text-center italic">
          Si aún no tienes una cuenta, completa los siguientes datos para crear
          tu usuario y acceder a todos nuestros beneficios.
        </p>

        <form className="flex flex-col gap-5" onSubmit={onSubmit}>
          {/* Usuario */}
          <div>
            <label className="block text-green-200 font-semibold mb-1">
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
            <label className="block text-green-200 font-semibold mb-1">
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
          {/* Boton */}
          <button
            type="submit"
            className="bg-green-800 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md flex items-center justify-center gap-2 transition-colors cursor-pointer"
          >
            <IoSaveSharp />
            Guardar
          </button>
        </form>
      </div>
    </div>
  );
}
