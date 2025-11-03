import { Link } from "react-router-dom"
import { GiArchiveRegister } from "react-icons/gi";
import { FaSearch } from "react-icons/fa";
import { IoNewspaperOutline } from "react-icons/io5";

export function Menu() {
    return (
        <div>
            <h1 className="text-white text-3xl font-bold text-center">Menu </h1>
            <p className="text-white font-serif text-center mt-4">¿Que desea realizar el dia de hoy?</p>

            <Link to="/doom">

                <button className="flex items-center justify-center gap-2 bg-green-700 hover:bg-green-600 text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300">
                   Registrar un Doom 
                    <GiArchiveRegister size={20} />
                </button>
            </Link>

            <Link to ="/search">
                <button className="flex items-center justify-center gap-2 bg-green-700 hover:bg-green-600 text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300 mt-6">
                Buscar un Doom 
                <FaSearch size={20} />
                </button>
            </Link>

            <Link to="/receipt">
                <button className="flex items-center justify-center gap-2 bg-green-700 hover:bg-green-600 text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300 mt-6">
                Consultar un recibo
                <IoNewspaperOutline size={20} />
                </button>
            </Link>

            <p className="text-white font-serif text-center mt-4">
                Ultimos Dom
            </p>

        </div>
    )
}