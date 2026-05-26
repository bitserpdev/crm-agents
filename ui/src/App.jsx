import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Campaigns    from "./pages/Campaigns";
import Connections  from "./pages/Connections";
import Runs         from "./pages/Runs";
import DataExplorer from "./pages/DataExplorer";
import Contacts     from "./pages/Contacts";
import EmailCampaigns from './pages/EmailCampaigns';
import FollowUps from './pages/FollowUps';
import Conversations from './pages/Conversations';
import Leads        from "./pages/Leads";
import { getHealth } from "./api/client";
export default function App() {
  const [health, setHealth] = useState("unknown");
  useEffect(() => {
    getHealth().then(r => setHealth(r.data.status)).catch(() => setHealth("degraded"));
    const i = setInterval(() =>
      getHealth().then(r => setHealth(r.data.status)).catch(() => setHealth("degraded"))
    , 30000);
    return () => clearInterval(i);
  }, []);
  return (
    <BrowserRouter>
      <Layout health={health}>
        <Routes>
          <Route path="/"            element={<Campaigns />} />
          <Route path="/connections" element={<Connections />} />
          <Route path="/runs"        element={<Runs />} />
          <Route path="/data"        element={<DataExplorer />} />
          <Route path="/contacts"    element={<Contacts />} />
          <Route path="/email-campaigns" element={<EmailCampaigns />}/>
          <Route path="/followups" element={<FollowUps />} />
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/leads"       element={<Leads />} />
	  <Route path="/followups" element={<FollowUps />} />
          <Route path="/conversations" element={<Conversations />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
