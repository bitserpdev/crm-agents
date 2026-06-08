export default function Field({ label, hint, children }) {
    return (
        <div>
            <label className="block text-xs font-medium text-gray-400 mb-1.5">{label}</label>
            {children}
            {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
        </div>
    );
}