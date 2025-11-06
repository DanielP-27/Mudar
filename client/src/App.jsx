import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { Navegation } from "./components/Navegation";
import { HomePage } from "./pages/HomePage";
import { Register } from "./pages/Register";
import { Login } from "./pages/Login";
import { Menu } from "./pages/Menu";
import Doms from "./pages/Doms"

function App() {
  return (
    <BrowserRouter>
      <div className="container mx-auto">
        <Toaster position="bottom-right" />
        <Navegation />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/menu" element={<Menu/>}/>
          <Route path="/doms" element={<Doms/>} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;



