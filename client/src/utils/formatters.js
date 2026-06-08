// src/utils/formatters.js
// Convierte string a integer (esto por diseño de arquitectura Django) — retorna null si está vacío
// actualmente solo se utiliza en PaginaCrearDom para hacer conversión de los campos nombre_cliente; tiempo_salida_almacen; rentabilidad; numero_factura
export const toInt = (valor) => valor !== '' ? parseInt(valor, 10) : null