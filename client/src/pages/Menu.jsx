import { Link } from "react-router-dom"
import { GiArchiveRegister } from "react-icons/gi";
import { FaSearch } from "react-icons/fa";
import { IoNewspaperOutline } from "react-icons/io5";
import { FiEdit } from "react-icons/fi";

export function Menu() {
    return (
        <div>
            <h1 className="text-white text-3xl font-bold text-center">Menu</h1>
            <p className="text-white font-bold text-center mt-4">¿Qué desea realizar el día de hoy?</p>

            {/* Contenedor de botones en horizontal */}
            <div className="flex flex-wrap gap-4 justify-center mt-6">
                
                {/* Botón Registrar */}
                <Link to="/doms" className="flex-1 min-w-[200px] max-w-[250px]">
                    <button className="w-full flex items-center justify-center gap-2 bg-[#2C7EC9] hover:bg-[#136EBF] text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300">
                        Registrar un Dom
                        <GiArchiveRegister size={20} />
                    </button>
                </Link>

                {/* Botón Editar */}
                <Link to="/doms/buscar" className="flex-1 min-w-[200px] max-w-[250px]">
                    <button className="w-full flex items-center justify-center gap-2 bg-[#2C7EC9] hover:bg-[#136EBF] text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300">
                        Editar un Dom
                        <FiEdit size={20} />
                    </button>
                </Link>

                {/* Botón Buscar */}
                <Link to="/doms/editar" className="flex-1 min-w-[200px] max-w-[250px]">
                    <button className="w-full flex items-center justify-center gap-2 bg-[#2C7EC9] hover:bg-[#136EBF] text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300">
                        Eliminar un Dom
                        <FaSearch size={20} />
                    </button>
                </Link>
            </div>

            <p className="text-white font-bold text-center mt-8">
                Últimos Dom
            </p>
        </div>
    )
}