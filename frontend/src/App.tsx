import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ClinicalShell } from '@/components/layout/ClinicalShell'
import { CinematicLayer } from '@/components/cinematic/CinematicLayer'
import { TitleSequence } from '@/components/cinematic/TitleSequence'
import { LoginPage } from '@/pages/LoginPage'
import { Dashboard } from '@/pages/Dashboard'
import { PatientWorkspace } from '@/pages/PatientWorkspace'
import { ComparePage } from '@/pages/ComparePage'
import { MemoryMapPage } from '@/pages/MemoryMapPage'
import { BoardPage } from '@/pages/BoardPage'

const INTRO_KEY = 'tr-intro-played'

export default function App() {
  const [showIntro, setShowIntro] = useState(
    () => sessionStorage.getItem(INTRO_KEY) !== 'done',
  )

  function finishIntro() {
    sessionStorage.setItem(INTRO_KEY, 'done')
    setShowIntro(false)
  }

  return (
    <BrowserRouter>
      <CinematicLayer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ClinicalShell />}>
          <Route index element={<Dashboard />} />
          <Route path="patient/:id" element={<PatientWorkspace />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="memory" element={<MemoryMapPage />} />
          <Route path="board" element={<BoardPage />} />
        </Route>
      </Routes>
      <AnimatePresence>
        {showIntro && <TitleSequence onComplete={finishIntro} />}
      </AnimatePresence>
    </BrowserRouter>
  )
}
