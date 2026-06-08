import { X } from "lucide-react";

export default function Modal({ title, onClose, children, wide = false }) {
    return (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
            <div className={`bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl
        ${wide ? "w-full max-w-4xl" : "w-full max-w-xl"} max-h-[90vh] overflow-auto`}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 sticky top-0 bg-gray-900">
                    <h3 className="font-semibold text-white">{title}</h3>
                    <button onClick={onClose} className="text-gray-500 hover:text-white">
                        <X size={18} />
                    </button>
                </div>
                <div className="p-6">{children}</div>
            </div>
        </div>
    );
}