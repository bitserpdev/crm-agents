import { useState } from "react";
import Modal from "../shared/Modal";

const INTENT = {
  hot: "bg-green-900/50 text-green-300",
  warm: "bg-yellow-900/50 text-yellow-300",
  cold: "bg-gray-800 text-gray-400",
  unsubscribe: "bg-red-900/50 text-red-300",
};

export default function PreviewEmailCampaignDetailModal({ isOpen, onClose, detail }) {
  const [tab, setTab] = useState("recipients");

  if (!isOpen || !detail) return null;

  return (
    <Modal title={`Campaign Results: ${detail.campaign.campaign_name}`} onClose={onClose} wide>
      {/* Run stats */}
      {detail.runs.length > 0 && (
        <div className="grid grid-cols-5 gap-2 mb-5">
          {[
            ["Total", detail.runs[0].total_recipients, "text-white"],
            ["Sent", detail.runs[0].sent_count, "text-green-400"],
            ["Failed", detail.runs[0].failed_count, "text-red-400"],
            ["Opens", detail.runs[0].open_count, "text-yellow-400"],
            ["Replies", detail.replies.length, "text-indigo-400"],
          ].map(([l, v, c]) => (
            <div key={l} className="bg-gray-800 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500">{l}</p>
              <p className={`text-xl font-bold ${c}`}>{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-gray-800 pb-2">
        <button onClick={() => setTab("recipients")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize
            ${tab === "recipients" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}>
          Recipients ({detail.recipients.length})
        </button>
        <button onClick={() => setTab("replies")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize
            ${tab === "replies" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}>
          Replies ({detail.replies.length})
        </button>
      </div>

      {tab === "recipients" && (
        <div className="space-y-1 max-h-80 overflow-auto">
          {detail.recipients.length === 0 ? (
            <p className="text-gray-600 text-sm text-center py-4">No emails sent yet</p>
          ) : (
            detail.recipients.map(r => (
              <div key={r.recipient_id} className="flex items-center justify-between py-2 border-b border-gray-800/50">
                <div>
                  <p className="text-sm text-white">{r.first_name} {r.last_name}</p>
                  <p className="text-xs text-gray-500">{r.company_name} · {r.email}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full
                  ${r.delivery_status === "sent" ? "bg-green-900/50 text-green-300"
                    : r.delivery_status === "failed" ? "bg-red-900/50 text-red-300"
                      : "bg-gray-800 text-gray-400"}`}>
                  {r.delivery_status}
                </span>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "replies" && (
        <div className="space-y-2 max-h-80 overflow-auto">
          {detail.replies.length === 0 ? (
            <p className="text-gray-600 text-sm text-center py-4">No replies yet</p>
          ) : (
            detail.replies.map(r => (
              <div key={r.response_id} className="bg-gray-800 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-white">{r.first_name} {r.last_name}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${INTENT[r.intent_label] || "bg-gray-700 text-gray-400"}`}>
                    {r.intent_label} · {r.intent_score?.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-gray-400 line-clamp-2">{r.reply_body}</p>
                <p className="text-xs text-gray-600 mt-1">{new Date(r.responded_at).toLocaleString()}</p>
              </div>
            ))
          )}
        </div>
      )}
    </Modal>
  );
}