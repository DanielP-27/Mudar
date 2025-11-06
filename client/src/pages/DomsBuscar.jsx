import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from 'axios';
import FormularioDom from '../components/FormularioDom'; // Ajusta la ruta según tu estructura

function DomsBuscar() {
    const navigate = useNavigate();
    const [domId, setDomId] = useState('');
    const [resultado, setResultado] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [mostrarFormulario, setMostrarFormulario] = useState(false);
    const [domParaEditar, setDomParaEditar] = useState(null);

    const handleBuscar = async (e) => {
        e.preventDefault();

        if (!domId.trim()){
            setError('Ingrese un id');
            return;
        }

        setLoading(true);
        setError(null);
        setResultado(null);

        try {
            const response = await axios.get(`http://localhost:8000/doms/${domId}`);
            
            // Adaptado para manejar diferentes formatos de respuesta
            const data = response.data.success ? response.data.data : response.data;
            setResultado(data);
            
        } catch (err) {
            console.error('Error:', err);
            setError(
                err.response?.status === 404 
                ? 'No se encontró un Dom con el ID suministrado'
                : 'Error al buscar el dom'
            );
        } finally {
            setLoading(false);
        }
    };

    const handleEditar = () => {
        setDomParaEditar(resultado);
        setMostrarFormulario(true);
    };

    const handleVolverBusqueda = () => {
        setMostrarFormulario(false);
        setDomParaEditar(null);
        // Opcional: limpiar búsqueda
        setResultado(null);
        setDomId('');
    };

    // Si se está editando, mostrar el formulario
    if (mostrarFormulario && domParaEditar) {
        return (
            <FormularioDom 
                domInicial={domParaEditar} 
                onVolver={handleVolverBusqueda}
                modoEdicion={true}
            />
        );
    }

    // Sino, mostrar la búsqueda
    return (
        <div className="min-h-screen bg-gray-800">
            <main className="container mx-auto px-4 py-8">
                <div className="mb-6">
                    <h2 className="text-3xl font-bold text-white mb-2">Buscar Dom para Editar</h2>
                    <p className="text-gray-300">Ingrese el ID del Dom que desea modificar</p>
                </div>

                {/* Barra de búsqueda */}
                <div className="bg-gray-700 rounded-lg p-6 mb-6">
                    <form onSubmit={handleBuscar} className="flex gap-4">
                        <input
                            type="number"
                            value={domId}
                            onChange={(e) => setDomId(e.target.value)}
                            placeholder="Ingrese ID del Dom"
                            className="flex-1 bg-gray-800 border-2 border-white text-white px-4 py-3 rounded focus:outline-none focus:border-green-500"
                            min="1"
                        />
                        <button
                            type="submit"
                            disabled={loading}
                            className="bg-[#2C7EC9] hover:bg-[#136EBF] text-white font-bold py-3 px-8 rounded-lg shadow-lg transition"
                        >
                            {loading ? 'Buscando...' : '🔍 Buscar'}
                        </button>
                    </form>
                </div>

                {/* Mensajes de error */}
                {error && (
                    <div className="bg-red-600 text-white px-4 py-3 rounded mb-6">
                        ⚠️ {error}
                    </div>
                )}

                {/* Resultado en FILA (ID + Cliente + Botón Editar) */}
                {resultado && (
                    <div className="bg-gray-700 rounded-lg p-4 mb-6">
                        <div className="flex items-center justify-between">
                            {/* Información en fila */}
                            <div className="flex gap-8 items-center">
                                <div>
                                    <p className="text-gray-400 text-sm">ID</p>
                                    <p className="text-green-400 font-bold text-xl">
                                        DOM-{resultado.dom_id}
                                    </p>
                                </div>
                                
                                <div>
                                    <p className="text-gray-400 text-sm">Cliente</p>
                                    <p className="text-white font-bold text-lg">
                                        {resultado.nombre_cliente}
                                    </p>
                                </div>
                            </div>

                            {/* Botón Editar */}
                            <button
                                onClick={handleEditar}
                                className="bg-green-700 hover:bg-green-600 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition flex items-center gap-2"
                            >
                                ✏️ Editar
                            </button>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

export default DomsBuscar;