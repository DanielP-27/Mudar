// src/main.jsx
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { ProveedorAutenticacion } from './context/AuthContext'
import App from './App'
import './index.css'

// Monta toda la app en el <div id="root"> del index.html
ReactDOM.createRoot(document.getElementById('root')).render(

  // Detecta problemas en desarrollo — sin efecto en producción
  <StrictMode>

    {/* Provee el estado de autenticación a toda la app */}
    <ProveedorAutenticacion>

      {/* Punto de entrada de la aplicación — contiene el router y las rutas */}
      <App />

    </ProveedorAutenticacion>

  </StrictMode>
)