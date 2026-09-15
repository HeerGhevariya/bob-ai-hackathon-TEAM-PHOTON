import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import TrialOverview from './components/TrialOverview'
import SiteLeaderboard from './components/SiteLeaderboard'
import SiteDetail from './components/SiteDetail'
import DeviationExplorer from './components/DeviationExplorer'
import CapaReport from './components/CapaReport'
import TrialGuardAssistant from './components/TrialGuardAssistant'
import GlobalMcpChat from './components/GlobalMcpChat'

export default function App() {
  const [selectedSiteId, setSelectedSiteId] = useState(null)
  const [capaReportSiteId, setCapaReportSiteId] = useState(null)

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<TrialOverview />} />
          <Route path="/chat" element={<GlobalMcpChat />} />
          <Route
            path="/sites"
            element={
              <SiteLeaderboard
                onSelectSite={(id) => setSelectedSiteId(id)}
                onGenerateCapa={(id) => setCapaReportSiteId(id)}
              />
            }
          />
          <Route
            path="/sites/:siteId"
            element={
              <SiteDetail onGenerateCapa={(id) => setCapaReportSiteId(id)} />
            }
          />
          <Route path="/deviations" element={<DeviationExplorer />} />
          <Route path="/capa" element={<CapaReport />} />
          <Route path="/capa/:siteId" element={<CapaReport />} />
        </Routes>
      </main>
      <TrialGuardAssistant />
    </div>
  )
}
