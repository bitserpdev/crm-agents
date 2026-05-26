import { NavLink } from "react-router-dom";
import { LayoutDashboard, Radio, PlayCircle, Database, Mail,
         Users, TrendingUp, Wifi, WifiOff, MessageSquare, Clock } from "lucide-react";

const links = [
  { to: "/",            label: "Campaigns",    icon: LayoutDashboard, group: "Agent 1" },
  { to: "/connections", label: "Connections",  icon: Radio,           group: "Agent 1" },
  { to: "/runs",        label: "Run History",  icon: PlayCircle,      group: "Agent 1" },
  { to: "/data",        label: "Raw Data",     icon: Database,        group: "Agent 1" },
  { to: "/contacts",    label: "Contacts",     icon: Users,           group: "Agent 2" },
  { to: "/leads",          label: "Leads",         icon: TrendingUp, group: "Agent 2" },
  { to: "/email-campaigns",label: "Email Campaigns",icon: Mail,       group: "Agent 3" },
  { to: "/conversations",  label: "Conversations",  icon: MessageSquare, group: "Agent 4" },
  { to: "/followups",      label: "Follow-ups",     icon: Clock,         group: "Agent 4" },
];

export default function Layout({ children, health }) {
  const groups = [...new Set(links.map(l => l.group))];
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      <aside className="w-60 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
        <div className="p-5 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white tracking-tight">BITS CRM</h1>
          <p className="text-xs text-gray-500 mt-0.5">Data Ingestion Platform</p>
        </div>
        <nav className="flex-1 p-3 space-y-4 overflow-auto">
          {groups.map(group => (
            <div key={group}>
              <p className="text-xs text-gray-600 font-medium uppercase tracking-wider px-3 mb-1">
                {group}
              </p>
              <div className="space-y-0.5">
                {links.filter(l => l.group === group).map(({ to, label, icon: Icon }) => (
                  <NavLink key={to} to={to} end={to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all
                       ${isActive ? "bg-indigo-600 text-white font-medium"
                                  : "text-gray-400 hover:bg-gray-800 hover:text-white"}`}>
                    <Icon size={15}/>{label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800">
          <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg
            ${health === "healthy" ? "bg-green-900/30 text-green-400" : "bg-red-900/30 text-red-400"}`}>
            {health === "healthy" ? <Wifi size={12}/> : <WifiOff size={12}/>}
            {health === "healthy" ? "All systems healthy" : "Service degraded"}
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-gray-950">{children}</main>
    </div>
  );
}
