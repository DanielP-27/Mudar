import { useState } from "react";
import axios from 'axios';

function DomsEliminar() {
    const [domId, setDomId] = useState('');
    const [resultado, setResultado] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [mostrarConfirmacion, setMostrarConfirmacion] = useState(false);
    const [eliminando, setEliminando] = useState(false);

    const handleBuscar = async (e) => {
        e.preventDefault();

        if (!domId.trim()){
            setError('Ingrese un ID');
            return;
        }

        setLoading(true);
        setError(null);
        setResultado(null);

        try {
            const response = await axios.get(`http://localhost:8000/doms/${domId}`);
            setResultado(response.data);
        } catch (err) {
            console.error('Error:', err);
            setError(
                err.response?.status === 404 
                ? 'No se encontró un DOM con el ID suministrado'
                : 'Error al buscar el DOM'
            );
        } finally {
            setLoading(false);
        }
    };

    const handleMostrarConfirmacion = () => {
        setMostrarConfirmacion(true);
    };

    const handleCancelarEliminacion = () => {
        setMostrarConfirmacion(false);
    };

    const handleEliminarDefinitivo = async () => {
        setEliminando(true);
        setError(null);

        try {
            const response = await axios.delete(`http://localhost:8000/doms/${resultado.dom_id}`);
            
            console.log(response)

            alert(`✅ DOM-${resultado.dom_id} de ${resultado.nombre_cliente} eliminado exitosamente`);
            
            // Limpiar formulario después de eliminar
            setResultado(null);
            setDomId('');
            setMostrarConfirmacion(false);
            
        } catch (err) {
            console.error('Error al eliminar:', err);
            setError(
                err.response?.data?.error || 
                'Error al eliminar el DOM. Intente nuevamente.'
            );
            setMostrarConfirmacion(false);
        } finally {
            setEliminando(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-800">
            <main className="container mx-auto px-4 py-8">
                <div className="mb-6">
                    <h2 className="text-3xl font-bold text-white mb-2">Eliminar Registro DOM</h2>
                    <p className="text-gray-300">Ingrese el ID del DOM que desea eliminar</p>
                </div>

                {/* Barra de búsqueda */}
                <div className="bg-gray-700 rounded-lg p-6 mb-6">
                    <form onSubmit={handleBuscar} className="flex gap-4">
                        <input
                            type="number"
                            value={domId}
                            onChange={(e) => setDomId(e.target.value)}
                            placeholder="Ingrese ID del DOM"
                            className="flex-1 bg-gray-800 border-2 border-white text-white px-4 py-3 rounded focus:outline-none focus:border-red-500"
                            min="1"
                            disabled={loading || mostrarConfirmacion}
                        />
                        <button
                            type="submit"
                            disabled={loading || mostrarConfirmacion}
                            className="bg-[#2C7EC9] hover:bg-[#136EBF] text-white font-bold py-3 px-8 rounded-lg shadow-lg transition disabled:opacity-50"
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

                {/* Resultado en FILA (ID + Cliente + Botón Eliminar) */}
                {resultado && !mostrarConfirmacion && (
                    <div className="bg-gray-700 rounded-lg p-4 mb-6">
                        <div className="flex items-center justify-between">
                            {/* Información en fila */}
                            <div className="flex gap-8 items-center">
                                <div>
                                    <p className="text-gray-400 text-sm">ID</p>
                                    <p className="text-red-400 font-bold text-xl">
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

                            {/* Botón Eliminar */}
                            <button
                                onClick={handleMostrarConfirmacion}
                                className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg transition flex items-center gap-2"
                            >
                                🗑️ Eliminar
                            </button>
                        </div>
                    </div>
                )}

                {/* Modal de Confirmación */}
                {mostrarConfirmacion && resultado && (
                    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
                        <div className="bg-gray-700 rounded-lg p-8 max-w-md w-full mx-4">
                            <div className="flex items-center gap-3 mb-4">
                                <span className="text-4xl">⚠️</span>
                                <h3 className="text-2xl font-bold text-white">
                                    ¿Está seguro?
                                </h3>
                            </div>

                            <p className="text-gray-300 mb-6">
                                ¿Desea eliminar definitivamente el siguiente registro?
                            </p>

                            <div className="bg-gray-800 rounded p-4 mb-6">
                                <p className="text-gray-400 text-sm">ID</p>
                                <p className="text-red-400 font-bold text-lg mb-2">
                                    DOM-{resultado.dom_id}
                                </p>
                                
                                <p className="text-gray-400 text-sm">Cliente</p>
                                <p className="text-white font-bold text-lg">
                                    {resultado.nombre_cliente}
                                </p>
                            </div>

                            <div className="bg-yellow-900 border-l-4 border-yellow-500 p-4 mb-6">
                                <p className="text-yellow-200 text-sm font-semibold">
                                    ⚠️ Esta acción no se puede deshacer
                                </p>
                            </div>

                            {error && (
                                <div className="bg-red-600 text-white px-4 py-3 rounded mb-4">
                                    ⚠️ {error}
                                </div>
                            )}

                            <div className="flex gap-4">
                                <button
                                    onClick={handleCancelarEliminacion}
                                    disabled={eliminando}
                                    className="flex-1 bg-gray-600 hover:bg-gray-500 text-white font-bold py-3 px-6 rounded-lg transition disabled:opacity-50"
                                >
                                    ✖️ Cancelar
                                </button>

                                <button
                                    onClick={handleEliminarDefinitivo}
                                    disabled={eliminando}
                                    className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition disabled:opacity-50"
                                >
                                    {eliminando ? '⏳ Eliminando...' : '🗑️ Eliminar Definitivamente'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

export default DomsEliminar;