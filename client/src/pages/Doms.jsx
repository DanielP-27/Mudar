import { useNavigate} from "react-router-dom";
import FormularioDom from "../components/FormularioDom"

function Doms () {
    const navigate = useNavigate ();

    const volverMenu = () => {
        navigate('/menu');
    };
    
    return (
      <div className="min-h-screen bg-gray-800">
        {/* Contenido principal */}
        <main className="container mx-auto px-4 py-8">
          <div className="mb-6">
            <h2 className="text-3xl font-bold text-white mb-2">Registrar Nuevo Dom</h2>
            <p className="text-gray-300">Complete el nombre del cliente para comenzar el registro</p>
          </div>

          {/* Formulario */}
          <FormularioDom />
        </main>
      </div>
    );
}

export default Doms;

