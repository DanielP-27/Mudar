// src/components/common/ModalMensaje.jsx
// Modal de mensajes al usuario (validaciones, errores de negocio, etc.).
// Es un envoltorio delgado sobre ModalBase: fija la variante `info` (ámbar + ⚠️)
// y un único botón "Entendido". Se conserva como componente propio para no tocar
// las llamadas existentes `<ModalMensaje abierto=... mensaje=... onCerrar=... />`.
// Soporta multilínea: si el mensaje trae varias líneas (unidas con '\n' por el
// util extraerMensajeError), ModalBase las renderiza como viñetas.

import ModalBase from './ModalBase'

function ModalMensaje({ abierto, titulo = 'Revise la información', mensaje, onCerrar }) {
  return (
    <ModalBase
      abierto={abierto}
      variante="info"
      titulo={titulo}
      mensaje={mensaje}
      onCerrar={onCerrar}
    />
  )
}

export default ModalMensaje
