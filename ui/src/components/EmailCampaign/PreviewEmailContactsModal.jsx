import { useState, useEffect } from "react";
import Modal from "../shared/Modal";
import { CheckSquare, Square, Send } from "lucide-react";

export default function PreviewEmailContactsModal({ isOpen, onClose, contacts, campaign, onSaveSelection }) {
  const [selectedContacts, setSelectedContacts] = useState({});

  useEffect(() => {
    if (contacts) {
      const selected = {};
      contacts.forEach(c => { selected[c.contact_id] = true; });
      setSelectedContacts(selected);
    }
  }, [contacts]);

  const toggleSelectAll = () => {
    const allSelected = contacts.every(c => selectedContacts[c.contact_id]);
    const newSelected = {};
    contacts.forEach(c => { newSelected[c.contact_id] = !allSelected; });
    setSelectedContacts(newSelected);
  };

  const toggleContact = (contactId) => {
    setSelectedContacts(prev => ({ ...prev, [contactId]: !prev[contactId] }));
  };

  const getSelectedContactsList = () => {
    return contacts.filter(c => selectedContacts[c.contact_id]).map(c => c.contact_id);
  };

  const handleSaveSelection = () => {
    const selectedIds = getSelectedContactsList();
    onSaveSelection(selectedIds);  // Save selected contacts to parent
    onClose();  // Close modal
  };

  if (!isOpen || !contacts) return null;

  return (
    <Modal title={`Preview Contacts (${contacts.length} total)`} onClose={onClose} wide>
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <button onClick={toggleSelectAll} className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300">
            {contacts.every(c => selectedContacts[c.contact_id]) ? (
              <><CheckSquare size={14} /> Deselect All</>
            ) : (
              <><Square size={14} /> Select All</>
            )}
          </button>
          <div className="text-xs text-gray-500">Selected: {getSelectedContactsList().length} contacts</div>
        </div>

        <div className="space-y-2 max-h-96 overflow-auto">
          {contacts.map(contact => (
            <div key={contact.contact_id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg hover:bg-gray-750">
              <div className="flex items-center gap-3">
                <button onClick={() => toggleContact(contact.contact_id)}>
                  {selectedContacts[contact.contact_id] ?
                    <CheckSquare size={18} className="text-indigo-400" /> :
                    <Square size={18} className="text-gray-500" />}
                </button>
                <div>
                  <p className="text-sm font-medium text-white">{contact.first_name} {contact.last_name}</p>
                  <p className="text-xs text-gray-400">{contact.job_title} · {contact.company_name || "No company"}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400">{contact.email}</p>
                <p className="text-xs text-gray-500">Score: {contact.overall_score || 0}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="flex gap-3 pt-4 border-t border-gray-800">
          <button onClick={handleSaveSelection} className="flex-1 bg-indigo-600 hover:bg-indigo-500 py-2.5 rounded-lg text-sm font-medium transition-colors">
            Save Selection ({getSelectedContactsList().length} contacts)
          </button>
          <button onClick={onClose} className="px-4 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">
            Cancel
          </button>
        </div>

      </div>
    </Modal>
  );
}