import Modal from "../shared/Modal";

export default function PreviewEmailCampaignModal({ isOpen, onClose, preview }) {
  if (!isOpen || !preview) return null;

  return (
    <Modal title="Email Preview" onClose={onClose} wide>
      {preview === "loading" ? (
        <div className="text-center py-8 text-gray-500">
          Generating personalized email with llama3.2...
        </div>
      ) : preview.error ? (
        <p className="text-red-400 text-sm">{preview.error}</p>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">To</label>
            <p className="text-sm text-white bg-gray-800 rounded-lg px-3 py-2">
              {preview.contact?.first_name} {preview.contact?.last_name} · {preview.contact?.email}
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Subject</label>
            <p className="text-sm font-medium text-indigo-300 bg-gray-800 rounded-lg px-3 py-2">{preview.email?.subject}</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Email Body (HTML)</label>
            <div className="bg-gray-800 rounded-lg p-4 text-sm text-gray-300 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: preview.email?.html || preview.email?.text }} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">Plain Text Version</label>
            <pre className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400 whitespace-pre-wrap max-h-32 overflow-auto">
              {preview.email?.text}
            </pre>
          </div>
        </div>
      )}
    </Modal>
  );
}