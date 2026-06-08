import { useState, useEffect } from "react";
import Modal from "../shared/Modal";
import Field from "../shared/Field";
import Input from "../shared/Input";
import Select from "../shared/Select";;

export default function CustomizeEmailCampaignModal({ isOpen, onClose, emailTemplate, onSave }) {
  const [template, setTemplate] = useState(emailTemplate || { subject: "", body: "", contact: null });

  useEffect(() => {
    if (emailTemplate) {
      setTemplate(emailTemplate);
    }
  }, [emailTemplate]);

  const handleSave = () => {
    onSave(template);
    onClose();
  };

  if (!isOpen || !emailTemplate) return null;

  return (
    <Modal title="Customize Email" onClose={onClose} wide>
      <div className="space-y-4">
        {template.contact && (
          <div className="bg-gray-800 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Sending to:</p>
            <p className="text-sm text-white">{template.contact.first_name} {template.contact.last_name}</p>
            <p className="text-xs text-gray-400">{template.contact.email} · {template.contact.company_name}</p>
          </div>
        )}

        <Field label="Subject Line" hint="Edit the email subject">
          <Input value={template.subject} onChange={v => setTemplate({ ...template, subject: v })} placeholder="Email subject" />
        </Field>

        <Field label="Email Body" hint="Edit the email content (HTML supported)">
          <Input value={template.body} onChange={v => setTemplate({ ...template, body: v })} placeholder="Email body" rows={10} />
        </Field>

        <div className="flex gap-3 pt-2">
          <button onClick={handleSave} className="flex-1 bg-indigo-600 hover:bg-indigo-500 py-2.5 rounded-lg text-sm font-medium transition-colors">
            Save & Send
          </button>
          <button onClick={onClose} className="px-4 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}