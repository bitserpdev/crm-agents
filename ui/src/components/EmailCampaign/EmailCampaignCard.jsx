import { Mail, Play, Eye, TrendingUp, Users, Edit3 } from "lucide-react";

export default function EmailCampaignCard({ campaign, onTrigger, onPreviewContacts, onCustomize, onOpenDetail, onLoadPreview, onEdit, onDelete, onConnectOutlook, isRunning }) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors">
            {/* Card header */}
            <div className="flex items-start justify-between mb-3">
                <div>
                    <h3 className="font-semibold text-white">{campaign.campaign_name}</h3>
                    <p className="text-xs text-gray-500 mt-0.5 truncate max-w-56">
                        {campaign.service_description}
                    </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium
          ${campaign.campaign_status === "running" ? "bg-green-900/50 text-green-300"
                        : campaign.campaign_status === "completed" ? "bg-blue-900/50 text-blue-300"
                            : "bg-gray-800 text-gray-400"}`}>
                    {campaign.campaign_status}
                </span>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-4 gap-2 mb-4">
                {[
                    ["Sent", campaign.total_sent || 0, "text-white"],
                    ["Runs", campaign.run_count || 0, "text-indigo-400"],
                    ["Score", `${campaign.filter_min_score || 0}-${campaign.filter_max_score || 100}`, "text-yellow-400"],
                    ["Stage", campaign.filter_stage || "all", "text-gray-400"],
                ].map(([label, val, color]) => (
                    <div key={label} className="bg-gray-800 rounded-lg p-2 text-center">
                        <p className="text-xs text-gray-500">{label}</p>
                        <p className={`text-sm font-bold ${color} truncate`}>{val}</p>
                    </div>
                ))}
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-1.5 mb-4">
                {campaign.filter_region && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">🌍 {campaign.filter_region}</span>}
                {campaign.filter_industry && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">🏭 {campaign.filter_industry}</span>}
                {campaign.filter_company_size && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">👥 {campaign.filter_company_size}</span>}
                {campaign.scheduled_at && <span className="text-xs bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded">⏰ {new Date(campaign.scheduled_at).toLocaleString()}</span>}
                {campaign.from_address && <span className="text-xs bg-indigo-900/30 text-indigo-400 px-2 py-0.5 rounded truncate max-w-36">✉ {campaign.from_address}</span>}
            </div>

            {/* Actions */}
            <div className="flex gap-2 flex-wrap">
                <button onClick={() => onPreviewContacts(campaign)}
                    className="flex items-center gap-1.5 bg-blue-700 hover:bg-blue-600 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors">
                    <Users size={11} /> Preview Contacts
                </button>

                <button onClick={() => onCustomize(campaign)}
                    className="flex items-center gap-1.5 bg-purple-700 hover:bg-purple-600 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors">
                    <Edit3 size={11} /> Customize
                </button>

                <button onClick={() => onTrigger(campaign.campaign_id, campaign.campaign_name)}
                    disabled={isRunning}
                    className="flex items-center gap-1.5 bg-indigo-700 hover:bg-indigo-600 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
                    <Play size={11} />{isRunning ? "Sending..." : "Send Now"}
                </button>

                <button onClick={() => onOpenDetail(campaign)}
                    className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                    <TrendingUp size={11} /> Results
                </button>

                <button onClick={() => onLoadPreview(campaign.campaign_id)}
                    className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                    <Eye size={11} /> Preview
                </button>

                <button onClick={() => onEdit(campaign)}
                    className="flex items-center gap-1.5 bg-yellow-700 hover:bg-yellow-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                    ✏️ Edit
                </button>

                <button onClick={() => onDelete(campaign.campaign_id, campaign.campaign_name)}
                    className="flex items-center gap-1.5 bg-red-800 hover:bg-red-700 px-3 py-1.5 rounded-lg text-xs transition-colors">
                    🗑️ Delete
                </button>

                {!campaign.azure_token && (
                    <button onClick={() => onConnectOutlook(campaign.campaign_id)}
                        className="flex items-center gap-1.5 bg-blue-800 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs transition-colors">
                        <Mail size={11} /> Connect Outlook
                    </button>
                )}
            </div>
        </div>
    );
}