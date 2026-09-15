import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Overview from './screens/Overview.jsx'
import ReserveMap from './screens/ReserveMap.jsx'
import Production from './screens/Production.jsx'
import RiskAnalysis from './screens/RiskAnalysis.jsx'
import DynamicSchedule from './screens/DynamicSchedule.jsx'
import Recommendations from './screens/Recommendations.jsx'
import SpotterAssistant from './screens/SpotterAssistant.jsx'
import Metrics from './screens/Metrics.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/reserve-map" element={<ReserveMap />} />
        <Route path="/production" element={<Production />} />
        <Route path="/risk-analysis" element={<RiskAnalysis />} />
        <Route path="/schedule" element={<DynamicSchedule />} />
        <Route path="/recommendations" element={<Recommendations />} />
        <Route path="/assistant" element={<SpotterAssistant />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  )
}
