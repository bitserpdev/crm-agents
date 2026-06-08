import { useEffect, useState } from "react";
import { getUpworkJobs, triggerProposal, getProposalStatus } from "../api/client";
import { RefreshCw, FileText, Loader2, CheckCircle, XCircle, Clock, Eye } from "lucide-react";

const STATUS_BADGE = {
  pending: { label: "No Proposal", color: "bg-gray-600/20 text-gray-400 border-gray-600/30" },
  running: { label: "Generating...", color: "bg-yellow-600/20 text-yellow-400 border-yellow-600/30" },
  pending_review: { label: "Pending Review", color: "bg-blue-600/20 text-blue-400 border-blue-600/30" },
  approved: { label: "Approved", color: "bg-green-600/20 text-green-400 border-green-600/30" },
  revision: { label: "Revision Needed", color: "bg-orange-600/20 text-orange-400 border-orange-600/30" },
  submitted: { label: "Submitted", color: "bg-purple-600/20 text-purple-400 border-purple-600/30" },
  accepted: { label: "Accepted! 🎉", color: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30" },
  failed: { label: "Failed", color: "bg-red-600/20 text-red-400 border-red-600/30" },
};

export default function UpworkJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState({});
  const [selectedJob, setSelectedJob] = useState(null);
  const [proposalModalOpen, setProposalModalOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await getUpworkJobs();
      if (response.status === 200) {
        setJobs(response?.data?.data || []);
      } else {
        console.error("Unexpected response status:", response.status);
      }
    } catch (error) {
      console.error("Failed to load Upwork jobs:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleTrigger = async (eventId) => {
    setTriggering(prev => ({ ...prev, [eventId]: true }));
    try {
      const response = await triggerProposal(eventId);
      const data = response.data;

      if (data.status === "completed" && data.proposal_text) {
        // update job in list with proposal directly from trigger response
        setJobs(prev => prev.map(job =>
          job.event_id === eventId
            ? {
              ...job,
              proposal_status: "pending_review",
              proposal: {
                text: data.proposal_text,
                subject: data.subject,
                review_status: data.review_status,
              }
            }
            : job
        ));
      }
    } catch (error) {
      console.error("Failed to trigger proposal:", error);
    } finally {
      setTriggering(prev => ({ ...prev, [eventId]: false }));
    }
  };

  const pollStatus = async (eventId) => {
    const interval = setInterval(async () => {
      try {
        const response = await getProposalStatus(eventId);
        const status = response.data?.status || response.status;

        // Update job status in the list
        setJobs(prev => prev.map(job =>
          job.event_id === eventId
            ? { ...job, proposal_status: status, proposal: response.data?.proposal }
            : job
        ));

        if (status === "completed" || status === "failed") {
          clearInterval(interval);
          setTriggering(prev => ({ ...prev, [eventId]: false }));
        }
      } catch (error) {
        console.error("Polling error:", error);
        clearInterval(interval);
        setTriggering(prev => ({ ...prev, [eventId]: false }));
      }
    }, 3000);

    // Stop polling after 2 minutes
    setTimeout(() => clearInterval(interval), 120000);
  };

  const viewProposal = (job) => {
    setSelectedJob(job);
    setProposalModalOpen(true);
  };

  const getStatusBadge = (status) => {
    const config = STATUS_BADGE[status] || STATUS_BADGE.pending;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium border ${config.color}`}>
        {status === "running" && <Loader2 size={10} className="animate-spin" />}
        {config.label}
      </span>
    );
  };

  const handleReview = async (proposalId, status, feedback = "") => {
    if (!proposalId) {
      console.error("No proposal ID found");
      return;
    }

    try {
      // Import your review API function (you need to create this in api/client.js)
      const { reviewProposal } = await import("../api/client");

      await reviewProposal(proposalId, status, feedback);

      if (status === "approved") {
        // Copy proposal text to clipboard
        const proposalText = selectedJob.proposal?.text || "";
        await navigator.clipboard.writeText(proposalText);
        alert("Proposal copied to clipboard!");
      }

      // Update local state
      setJobs(prev => prev.map(job =>
        job.event_id === selectedJob.event_id
          ? { ...job, proposal_status: status === "approved" ? "approved" : "revision" }
          : job
      ));

      // Close modal if approved
      if (status === "approved") {
        setProposalModalOpen(false);
      }
    } catch (error) {
      console.error("Review failed:", error);
      alert("Failed to submit review. Please try again.");
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Upwork Jobs</h2>
          <p className="text-sm text-gray-500 mt-1">Fetched jobs and proposal status</p>
        </div>
        <button onClick={load}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stats summary */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Jobs", value: jobs.length, color: "text-blue-400" },
          { label: "Pending", value: jobs.filter(j => !j.proposal_status || j.proposal_status === "pending").length, color: "text-gray-400" },
          { label: "In Progress", value: jobs.filter(j => j.proposal_status === "running").length, color: "text-yellow-400" },
          { label: "Accepted", value: jobs.filter(j => j.proposal_status === "accepted").length, color: "text-green-400" },
        ].map(stat => (
          <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Jobs table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Title</th>
              <th className="text-left px-5 py-3">Budget</th>
              <th className="text-left px-5 py-3">Experience</th>
              <th className="text-left px-5 py-3">Posted</th>
              <th className="text-left px-5 py-3">Status</th>
              <th className="text-left px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-600 text-sm">
                  <Loader2 size={20} className="animate-spin mx-auto mb-2" />
                  Loading jobs...
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-gray-600 text-sm">
                  No Upwork jobs found. Run an Upwork campaign first.
                </td>
              </tr>
            ) : (
              jobs.map(job => (
                <tr key={job.event_id} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="max-w-md">
                      <p className="text-sm font-medium text-white truncate">{job.title}</p>
                      <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-500 truncate">
                        {job.url?.slice(0, 50)}...
                      </a>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-300">
                    {job.budget ? `$${job.budget}` : "—"}
                  </td>
                  <td className="px-5 py-3 text-sm text-gray-300 capitalize">
                    {job.experience_level || "—"}
                  </td>
                  <td className="px-5 py-3 text-xs text-gray-400">
                    {job.posted_date ? new Date(job.posted_date).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-5 py-3">
                    {getStatusBadge(job.proposal_status || "pending")}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex gap-2">
                      {(!job.proposal_status || job.proposal_status === "pending") && (
                        <button
                          onClick={() => handleTrigger(job.event_id)}
                          disabled={triggering[job.event_id]}
                          className="flex items-center gap-1.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-400 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                        >
                          {triggering[job.event_id] ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <FileText size={12} />
                          )}
                          {triggering[job.event_id] ? "Generating..." : "Write Proposal"}
                        </button>
                      )}
                      {(job.proposal_status === "pending_review" || job.proposal_status === "approved") && (
                        <button
                          onClick={() => viewProposal(job)}
                          className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs font-medium"
                        >
                          <Eye size={12} /> View Proposal
                        </button>
                      )}
                      {job.proposal_status === "accepted" && (
                        <span className="flex items-center gap-1.5 text-green-400 text-xs">
                          <CheckCircle size={12} /> Won!
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Proposal Modal */}
      {proposalModalOpen && selectedJob && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h3 className="font-semibold text-white">Proposal</h3>
              <button onClick={() => setProposalModalOpen(false)} className="text-gray-500 hover:text-white">
                <XCircle size={20} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1">
              <h4 className="text-lg font-semibold text-white mb-2">{selectedJob.title}</h4>
              <div className="prose prose-invert max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-gray-300 text-sm bg-gray-800/50 p-4 rounded-lg">
                  {selectedJob.proposal?.text || "No proposal text available"}
                </pre>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-800 flex justify-end gap-3">
              <button
                onClick={() => setProposalModalOpen(false)}
                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => handleReview(selectedJob.proposal?.proposal_id, "revision")}
                className="px-4 py-2 bg-orange-600/20 hover:bg-orange-600/30 border border-orange-500/30 text-orange-400 rounded-lg text-sm transition-colors"
              >
                Request Revision
              </button>
              <button
                onClick={() => handleReview(selectedJob.proposal?.proposal_id, "approved")}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Approve & Copy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}