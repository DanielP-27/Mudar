import { useParams, useNavigate } from 'react-router-dom';
import FormularioDom from '../components/FormularioDom';

function DomsEditar() {
  const { id } = useParams(); // Obtener ID de la URL
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-800">

      <main className="container mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-white mb-2">Editar Dom</h2>
          <p className="text-gray-300">Modifique los campos necesarios</p>
        </div>

        {/* Reutilizar FormularioDom pasando el ID */}
        <FormularioDom domId={parseInt(id)} />
      </main>
    </div>
  );
}

export default DomsEditar;