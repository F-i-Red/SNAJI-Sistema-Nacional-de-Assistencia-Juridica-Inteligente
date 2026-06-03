import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import Layout from './components/Layout'
import PaginaLogin from './pages/Login'
import PaginaDashboard from './pages/Dashboard'
import PaginaConsulta from './pages/Consulta'
import PaginaProcessos from './pages/Processos'
import PaginaDocumentos from './pages/Documentos'
import PaginaAuditoria from './pages/Auditoria'
import PaginaAudiencias from './pages/Audiencias'
import { useAuthStore } from './auth/session'

function RotaProtegida({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const { restaurarSessao } = useAuthStore()
  useEffect(() => { restaurarSessao() }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<PaginaLogin />} />
        <Route path="/" element={<RotaProtegida><Layout /></RotaProtegida>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"  element={<PaginaDashboard />} />
          <Route path="consulta"   element={<PaginaConsulta />} />
          <Route path="processos"  element={<PaginaProcessos />} />
          <Route path="documentos" element={<PaginaDocumentos />} />
          <Route path="audiencias" element={<PaginaAudiencias />} />
          <Route path="auditoria"  element={<PaginaAuditoria />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
