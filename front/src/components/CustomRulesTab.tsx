import React, { useState, useEffect } from 'react';

interface CustomRule {
  id: number;
  engine_name: string;
  rule_name: string;
  rule_content: string;
  enabled: number;
  category: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

const CustomRulesTab: React.FC = () => {
  const [rules, setRules] = useState<CustomRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const [showDeleteToast, setShowDeleteToast] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<number | null>(null);
  const [newRule, setNewRule] = useState({
    rule_name: '',
    pattern: '',
    description: '',
  });

  // Fixed to PII Leak Engine only
  const ENGINE_NAME = 'pii_leak_engine';

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async (showLoading: boolean = true) => {
    try {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);
      const data = await window.electronAPI.getCustomRules(ENGINE_NAME);
      setRules(data.rules || []);
    } catch (error) {
      console.error('Failed to load custom rules:', error);
      setError(error instanceof Error ? error.message : 'Failed to load custom rules. Make sure the server is running on port 8282.');
      setRules([]);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
    }
  };

  const handleAddRule = async () => {
    if (!newRule.rule_name || !newRule.pattern) {
      alert('Rule name and detection pattern are required');
      return;
    }

    // Auto-generate YARA rule from user input (category fixed to PII)
    const rule_content = `rule ${newRule.rule_name} {
    meta:
        category = "PII"
        description = "${newRule.description || newRule.rule_name}"
    strings:
        $pattern = "${newRule.pattern}"
    condition:
        $pattern
}`;

    try {
      const data = await window.electronAPI.addCustomRule({
        engine_name: ENGINE_NAME,
        rule_name: newRule.rule_name,
        rule_content: rule_content,
        category: 'PII',
        description: newRule.description || newRule.rule_name,
      });

      if (data.success) {
        // Close modal and reset form immediately
        setShowAddModal(false);
        setNewRule({ rule_name: '', pattern: '', description: '' });
        // Show success toast
        setShowSuccessToast(true);
        setTimeout(() => setShowSuccessToast(false), 3000);
        // Reload rules in background
        loadRules(false);
      } else {
        const errorMsg = data.error?.includes('UNIQUE constraint') || data.error?.includes('insert custom rule')
          ? 'A rule with the same name already exists. Please use a different name.'
          : `Failed to add rule: ${data.error}`;
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Failed to add custom rule:', error);
      alert('Failed to add custom rule');
    }
  };

  const handleToggleRule = async (ruleId: number, currentEnabled: number) => {
    try {
      const data = await window.electronAPI.toggleCustomRule(
        ruleId,
        currentEnabled === 1 ? false : true
      );

      if (data.success) {
        loadRules(false);
      } else {
        alert(`Failed to toggle rule: ${data.error}`);
      }
    } catch (error) {
      console.error('Failed to toggle custom rule:', error);
      alert('Failed to toggle custom rule');
    }
  };

  const handleDeleteRule = (ruleId: number) => {
    setRuleToDelete(ruleId);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (ruleToDelete === null) return;

    setShowDeleteConfirm(false);

    try {
      const data = await window.electronAPI.deleteCustomRule(ruleToDelete);

      if (data.success) {
        // Show delete success toast
        setShowDeleteToast(true);
        setTimeout(() => setShowDeleteToast(false), 3000);
        // Reload rules in background
        loadRules(false);
      } else {
        alert(`Failed to delete rule: ${data.error}`);
      }
    } catch (error) {
      console.error('Failed to delete custom rule:', error);
      alert('Failed to delete custom rule');
    } finally {
      setRuleToDelete(null);
    }
  };

  return (
    <div className="space-y-4 relative">
      {/* Success Toast */}
      {showSuccessToast && (
        <div className="fixed top-4 right-4 bg-white border-l-4 border-green-500 px-6 py-3 rounded-lg shadow-xl z-50 flex items-center gap-3 animate-slide-left">
          <div className="shrink-0 w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <span className="text-gray-800 font-medium">Rule added successfully!</span>
        </div>
      )}

      {/* Delete Toast */}
      {showDeleteToast && (
        <div className="fixed top-4 right-4 bg-white border-l-4 border-red-500 px-6 py-3 rounded-lg shadow-xl z-50 flex items-center gap-3 animate-slide-left">
          <div className="shrink-0 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
          <span className="text-gray-800 font-medium">Rule removed successfully!</span>
        </div>
      )}

      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-base font-semibold">Custom PII Rules</h3>
          <p className="text-xs text-gray-600 mt-0.5">Add custom detection patterns</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-2.5 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 whitespace-nowrap flex-shrink-0"
        >
          + Add
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8">Loading rules...</div>
      ) : error ? (
        <div className="text-center py-8">
          <div className="text-red-500 mb-2">Failed to load custom rules</div>
          <div className="text-sm text-gray-600">{error}</div>
          <button
            onClick={() => loadRules()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      ) : rules.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No custom rules found for this engine.
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="border border-gray-200 rounded p-3 bg-white"
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1">
                  <h4 className="font-semibold text-base">{rule.rule_name}</h4>
                  {rule.description && (
                    <p className="text-xs text-gray-600 mt-1">{rule.description}</p>
                  )}
                  {rule.category && (
                    <span className="inline-block mt-1.5 px-2 py-0.5 text-xs bg-blue-100 text-blue-800 rounded">
                      {rule.category}
                    </span>
                  )}
                </div>
                <div className="flex gap-2 ml-4">
                  <button
                    onClick={() => handleToggleRule(rule.id, rule.enabled)}
                    className={`px-2.5 py-1 rounded text-xs ${
                      rule.enabled === 1
                        ? 'bg-green-100 text-green-800 hover:bg-green-200'
                        : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                    }`}
                  >
                    {rule.enabled === 1 ? 'Enabled' : 'Disabled'}
                  </button>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="px-2.5 py-1 bg-red-100 text-red-800 rounded text-xs hover:bg-red-200"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-2 bg-gray-50 p-2 rounded">
                <div className="text-xs font-medium text-gray-700 mb-1">Detection Pattern:</div>
                <div className="text-xs font-mono bg-white px-2 py-1 rounded border border-gray-200">
                  {rule.rule_content.match(/\$pattern = "(.+?)"/)?.[1] || 'N/A'}
                </div>
              </div>
              <div className="mt-1.5 text-xs text-gray-500">
                Created: {new Date(rule.created_at).toLocaleString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-white/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            <h3 className="text-xl font-semibold mb-4">Add Custom Detection Rule</h3>
            <p className="text-sm text-gray-600 mb-4">
              Create a simple detection rule by providing a name and the text pattern to detect.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Rule Name *</label>
                <input
                  type="text"
                  value={newRule.rule_name}
                  onChange={(e) => setNewRule({ ...newRule, rule_name: e.target.value })}
                  placeholder="e.g., MySecretKey"
                  className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">A unique name for this rule (no spaces)</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Detection Pattern *</label>
                <input
                  type="text"
                  value={newRule.pattern}
                  onChange={(e) => setNewRule({ ...newRule, pattern: e.target.value })}
                  placeholder="e.g., MY_SECRET_KEY"
                  className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">The text pattern to detect in communications</p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Description (Optional)</label>
                <input
                  type="text"
                  value={newRule.description}
                  onChange={(e) => setNewRule({ ...newRule, description: e.target.value })}
                  placeholder="e.g., Detects my application secret key"
                  className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setNewRule({ rule_name: '', pattern: '', description: '' });
                }}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddRule}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Add Rule
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-white/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-semibold mb-4">Delete Rule</h3>
            <p className="text-sm text-gray-600 mb-6">
              Are you sure you want to delete this rule? This action cannot be undone.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setRuleToDelete(null);
                }}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomRulesTab;
