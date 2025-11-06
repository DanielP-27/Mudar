import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
//import './FormularioDom.css'; // Opcional

function FormularioDom() {
    const navigate = useNavigate();
    
    // Estados del formulario - como en el modelo Django
    const [formData, setFormData] = useState({
        // Campo obligatorio
        nombre_cliente: '',
        
        // Campos opcionales - DateField
        fecha_entrega: '',
        fecha_produccion: '',
        fecha_tratamiento: '',
        
        // Campos opcionales - IntegerField
        orden_produccion: '',
        cantidad_elaborada: '',
        cantidad_pendiente: '',
        orden_tratamiento: '',
        
        // Campos opcionales - CharField con choices
        lider_produccion: 'SIN_LIDER',
        lider_almacen: 'SIN_LIDER',
        
        // Campos opcionales - BooleanField (ahora con select)
        materia_prima_disponible: false,
        requiere_prealistamiento: false,
        necesita_carton: false,
        grafado_fundas: false,
        cliente_recoge: true,  // default=True en el modelo
        mudar_entrega: false,
        tratamiento_realizado: false,   
    });

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    // Exactamente como en el modelo Django
    const LIDERES = [
        { value: 'SIN_LIDER', label: '-- Seleccione un líder --' },
        { value: 'ALEX_AREVALO', label: 'Alex Arevalo' },
        { value: 'JULIO_MARTINEZ', label: 'Julio Martinez' },
        { value: 'LUIS_MANRIQUE', label: 'Luis Manrique' },
        { value: 'JHON_MONTERREY', label: 'Jhon Monterrey' },
    ];

    // Opciones Sí/No para BooleanFields
    const OPCIONES_SINO = [
        { value: false, label: 'No' },
        { value: true, label: 'Sí' },
    ];

    // con esta constante, se maneja los cambios en los campos tipo texto, fecha, número y select

    const handleChange = (e) =>{
        const { name, value, type} = e.target;

        // conversion de "numeros" de strings a numbers
        if (type === 'number') {
            setFormData({
                ...formData,
                [name]: value === '' ? '' : Number(value)
            });
        }

        // conversion para los selects boleeanos, de string a boleean
        else if (value === 'true' || value === 'false'){
            setFormData({
                ...formData,
                [name]: value === 'true'
            });
        }

        // Para los demás tipos de datos
        else {
            setFormData({
                ...formData,
                [name]: value
            })
        };
    }

    //  se preparan los datos para ser enviados al backend

    const prepararDatos  = () => {
        const datos = {};

        // Nombre cliente (obligatorio - CharField)
        datos.nombre_cliente = formData.nombre_cliente.trim();
        
        // DateField: enviar null si está vacío, string si tiene valor
        datos.fecha_entrega = formData.fecha_entrega || null;
        datos.fecha_produccion = formData.fecha_produccion || null;
        datos.fecha_tratamiento = formData.fecha_tratamiento || null;
        
        // IntegerField: enviar null si está vacío, número si tiene valor
        datos.orden_produccion = formData.orden_produccion === '' ? null : formData.orden_produccion;
        datos.cantidad_elaborada = formData.cantidad_elaborada === '' ? null : formData.cantidad_elaborada;
        datos.cantidad_pendiente = formData.cantidad_pendiente === '' ? null : formData.cantidad_pendiente;
        datos.orden_tratamiento = formData.orden_tratamiento === '' ? null : formData.orden_tratamiento;
        
        // CharField con choices: enviar null si es 'SIN_LIDER', valor si tiene selección
        datos.lider_produccion = formData.lider_produccion === 'SIN_LIDER' ? null : formData.lider_produccion;
        datos.lider_almacen = formData.lider_almacen === 'SIN_LIDER' ? null : formData.lider_almacen;
        
        // BooleanField: enviar true/false directamente
        datos.materia_prima_disponible = formData.materia_prima_disponible;
        datos.requiere_prealistamiento = formData.requiere_prealistamiento;
        datos.necesita_carton = formData.necesita_carton;
        datos.grafado_fundas = formData.grafado_fundas;
        datos.cliente_recoge = formData.cliente_recoge;
        datos.mudar_entrega = formData.mudar_entrega;
        datos.tratamiento_realizado = formData.tratamiento_realizado;

        return datos;
    };

    // constante para el envío del formulario
    const handleSubmit = async (e) => {
        e.preventDefault();
        
        // Validación: solo nombre_cliente es obligatorio
        if (!formData.nombre_cliente.trim()) {
        setError('El nombre del cliente es obligatorio');
        return;
        }

        setLoading(true);
        setError(null);

        try {
        const datosEnviar = prepararDatos();
        console.log('Datos a enviar:', datosEnviar); // Para debugging
        
        const response = await axios.post('http://localhost:8000/doms', datosEnviar);
        
        if (response.data.success) {
            setSuccess(true);
            
            // Redirigir después de 2 segundos
            setTimeout(() => {
            navigate('/menu');
            }, 2000);
        }
        } catch (err) {
        console.error('Error al registrar Dom:', err);
        
        // Manejar errores específicos del backend
        if (err.response?.data?.errors) {
            const errores = err.response.data.errors;
            const mensajesError = Object.keys(errores).map(
            campo => `${campo}: ${errores[campo].join(', ')}`
            ).join('\n');
            setError(mensajesError);
        } else {
            setError(
            err.response?.data?.message || 
            'Error al registrar el Dom. Intente nuevamente.'
            );
        }
        } finally {
        setLoading(false);
        }
    };

      return (
    <div className="bg-gray-800 rounded-lg shadow-xl p-6">
      <form onSubmit={handleSubmit} className="space-y-8">
        
        {/* SECCIÓN 1: INFORMACIÓN BÁSICA */}
        <div className="space-y-4">
          <h3 className="text-xl font-bold text-white border-b border-white pb-2">Información Básica</h3>
          
          <div>
            <label htmlFor="nombre_cliente" className="block text-white font-semibold mb-2">
              Nombre del Cliente <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="nombre_cliente"
              name="nombre_cliente"
              value={formData.nombre_cliente}
              onChange={handleChange}
              placeholder="Ingrese el nombre del cliente"
              disabled={loading}
              className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              required
              maxLength={200}
            />
          </div>
        </div>

        {/* SECCIÓN 2: PRODUCCIÓN */}
        <div className="space-y-4">
          <h3 className="text-xl font-bold text-white border-b border-white pb-2">Información de Producción</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="fecha_entrega" className="block text-white font-semibold mb-2">
                Fecha de Entrega
              </label>
              <input
                type="date"
                id="fecha_entrega"
                name="fecha_entrega"
                value={formData.fecha_entrega}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              />
            </div>

            <div>
              <label htmlFor="orden_produccion" className="block text-white font-semibold mb-2">
                Orden de Producción
              </label>
              <input
                type="number"
                id="orden_produccion"
                name="orden_produccion"
                value={formData.orden_produccion}
                onChange={handleChange}
                placeholder="Número de orden"
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
                min="0"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="fecha_produccion" className="block text-white font-semibold mb-2">
                Fecha de Producción
              </label>
              <input
                type="date"
                id="fecha_produccion"
                name="fecha_produccion"
                value={formData.fecha_produccion}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              />
            </div>

            <div>
              <label htmlFor="lider_produccion" className="block text-white font-semibold mb-2">
                Líder de Producción
              </label>
              <select
                id="lider_produccion"
                name="lider_produccion"
                value={formData.lider_produccion}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {LIDERES.map(lider => (
                  <option key={lider.value} value={lider.value}>
                    {lider.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="cantidad_elaborada" className="block text-white font-semibold mb-2">
                Cantidad Elaborada
              </label>
              <input
                type="number"
                id="cantidad_elaborada"
                name="cantidad_elaborada"
                value={formData.cantidad_elaborada}
                onChange={handleChange}
                placeholder="0"
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
                min="0"
              />
            </div>

            <div>
              <label htmlFor="cantidad_pendiente" className="block text-white font-semibold mb-2">
                Cantidad Pendiente
              </label>
              <input
                type="number"
                id="cantidad_pendiente"
                name="cantidad_pendiente"
                value={formData.cantidad_pendiente}
                onChange={handleChange}
                placeholder="0"
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
                min="0"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="materia_prima_disponible" className="block text-white font-semibold mb-2">
                Materia Prima Disponible
              </label>
              <select
                id="materia_prima_disponible"
                name="materia_prima_disponible"
                value={formData.materia_prima_disponible}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="requiere_prealistamiento" className="block text-white font-semibold mb-2">
                Requiere Prealistamiento
              </label>
              <select
                id="requiere_prealistamiento"
                name="requiere_prealistamiento"
                value={formData.requiere_prealistamiento}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="necesita_carton" className="block text-white font-semibold mb-2">
                Necesita Cartón
              </label>
              <select
                id="necesita_carton"
                name="necesita_carton"
                value={formData.necesita_carton}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="grafado_fundas" className="block text-white font-semibold mb-2">
                Grafado de Fundas
              </label>
              <select
                id="grafado_fundas"
                name="grafado_fundas"
                value={formData.grafado_fundas}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* SECCIÓN 3: ALMACÉN Y TRATAMIENTO */}
        <div className="space-y-4">
          <h3 className="text-xl font-bold text-white border-b border-white pb-2">Almacén y Tratamiento</h3>
          
          <div>
            <label htmlFor="lider_almacen" className="block text-white font-semibold mb-2">
              Líder de Almacén
            </label>
            <select
              id="lider_almacen"
              name="lider_almacen"
              value={formData.lider_almacen}
              onChange={handleChange}
              disabled={loading}
              className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
            >
              {LIDERES.map(lider => (
                <option key={lider.value} value={lider.value}>
                  {lider.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="fecha_tratamiento" className="block text-white font-semibold mb-2">
                Fecha de Tratamiento
              </label>
              <input
                type="date"
                id="fecha_tratamiento"
                name="fecha_tratamiento"
                value={formData.fecha_tratamiento}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              />
            </div>

            <div>
              <label htmlFor="orden_tratamiento" className="block text-white font-semibold mb-2">
                Orden de Tratamiento
              </label>
              <input
                type="number"
                id="orden_tratamiento"
                name="orden_tratamiento"
                value={formData.orden_tratamiento}
                onChange={handleChange}
                placeholder="Número de orden"
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
                min="0"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="cliente_recoge" className="block text-white font-semibold mb-2">
                Cliente Recoge
              </label>
              <select
                id="cliente_recoge"
                name="cliente_recoge"
                value={formData.cliente_recoge}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="mudar_entrega" className="block text-white font-semibold mb-2">
                Mudar Entrega
              </label>
              <select
                id="mudar_entrega"
                name="mudar_entrega"
                value={formData.mudar_entrega}
                onChange={handleChange}
                disabled={loading}
                className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
              >
                {OPCIONES_SINO.map(opcion => (
                  <option key={opcion.value.toString()} value={opcion.value}>
                    {opcion.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="tratamiento_realizado" className="block text-white font-semibold mb-2">
              Tratamiento Realizado
            </label>
            <select
              id="tratamiento_realizado"
              name="tratamiento_realizado"
              value={formData.tratamiento_realizado}
              onChange={handleChange}
              disabled={loading}
              className="w-full bg-gray-800 border-2 border-white text-white px-4 py-2 rounded focus:outline-none focus:border-green-500 transition"
            >
              {OPCIONES_SINO.map(opcion => (
                <option key={opcion.value.toString()} value={opcion.value}>
                  {opcion.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Mensajes */}
        {error && (
          <div className="bg-red-600 text-white px-4 py-3 rounded">
            ⚠️ {error}
          </div>
        )}

        {success && (
          <div className="bg-green-600 text-white px-4 py-3 rounded">
            ✅ Dom registrado exitosamente. Redirigiendo...
          </div>
        )}

        {/* Botones */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={loading}
            className="flex-1 bg-green-700 hover:bg-green-600 text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Registrando...' : '🏠 Registrar Dom'}
          </button>
          
          <button
            type="button"
            onClick={() => navigate('/menu')}
            disabled={loading}
            className="flex-1 bg-gray-600 hover:bg-gray-500 text-white font-bold py-3 px-6 rounded-lg shadow-lg transform hover:scale-105 transition duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );    
}

export default FormularioDom;

