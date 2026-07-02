import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Send, ShieldAlert, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

export default function AssessmentWorkspace({ 
  activePayload, setActivePayload, 
  assessmentResult, setAssessmentResult, 
  hasAssessed, setHasAssessed,
  setChatHistory,
  API_BASE_URL 
}: any) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/rules`)
      .then(res => console.log("Rules loaded:", res.data))
      .catch(err => console.error("Error fetching rules:", err));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as any;
    setActivePayload({
      ...activePayload,
      [name]: type === 'number' ? Number(value) : value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setHasAssessed(false);
    setAssessmentResult(null);
    setChatHistory([]);
    try {
      const res = await axios.post(`${API_BASE_URL}/assess`, { payload: activePayload });
      setAssessmentResult(res.data.result);
      setHasAssessed(true);
    } catch (err) {
      console.error("Assessment failed", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="hero">
        <h1>Intelligent Loan Eligibility AI Agent</h1>
        <p>AI-powered underwriting and policy engine</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: '2rem' }}>
        {/* Form Panel */}
        <div className="card">
          <h3 style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
            Customer Application Profile
          </h3>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="input-group">
                <label>Age</label>
                <input type="number" className="input" name="age" value={activePayload.age || ''} onChange={handleChange} required min="18" max="75" />
              </div>
              <div className="input-group">
                <label>Monthly Income (₹)</label>
                <input type="number" className="input" name="monthly_income" value={activePayload.monthly_income || ''} onChange={handleChange} required />
              </div>
              <div className="input-group">
                <label>Credit Score</label>
                <input type="number" className="input" name="credit_score" value={activePayload.credit_score || ''} onChange={handleChange} required min="300" max="900" />
              </div>
              <div className="input-group">
                <label>Employment Type</label>
                <select className="select" name="employment_type" value={activePayload.employment_type || ''} onChange={handleChange} required>
                  <option value="">-- Select --</option>
                  <option value="Salaried">Salaried</option>
                  <option value="Self-employed">Self-employed</option>
                  <option value="Business">Business</option>
                  <option value="Student">Student</option>
                  <option value="Unemployed">Unemployed</option>
                </select>
              </div>
              <div className="input-group">
                <label>Existing Loan</label>
                <select className="select" name="existing_loan" value={activePayload.existing_loan || ''} onChange={handleChange} required>
                  <option value="">-- Select --</option>
                  <option value="Yes">Yes</option>
                  <option value="No">No</option>
                </select>
              </div>
              {activePayload.existing_loan === 'Yes' && (
                <div className="input-group">
                  <label>Monthly EMI (₹)</label>
                  <input type="number" className="input" name="monthly_loan_payment" value={activePayload.monthly_loan_payment || ''} onChange={handleChange} required />
                </div>
              )}
              <div className="input-group">
                <label>Requested Amount (₹)</label>
                <input type="number" className="input" name="loan_amount_requested" value={activePayload.loan_amount_requested || ''} onChange={handleChange} required />
              </div>
              <div className="input-group">
                <label>Loan Purpose</label>
                <select className="select" name="loan_purpose" value={activePayload.loan_purpose || ''} onChange={handleChange} required>
                  <option value="Home Renovation">Home Renovation</option>
                  <option value="Medical Emergency">Medical Emergency</option>
                  <option value="Education">Education</option>
                  <option value="Business Expansion">Business Expansion</option>
                  <option value="General Purchase">General Purchase</option>
                </select>
              </div>
            </div>

            <button type="submit" className="btn" style={{ width: '100%', marginTop: '1rem' }} disabled={loading}>
              {loading ? 'Running AI Pipeline...' : 'Launch Assessment'}
              <Send size={18} />
            </button>
          </form>
        </div>

        {/* Results Panel */}
        <div className="card">
          <h3 style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
            AI Loan Assessment Verdict
          </h3>

          {!hasAssessed && !loading ? (
            <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
              Fill out the Customer Profile and click "Launch Assessment" to run the evaluation.
            </div>
          ) : loading ? (
            <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
              <div style={{ marginBottom: '1rem', color: 'var(--primary)' }}>Verifying input parameters...</div>
              <div style={{ marginBottom: '1rem', color: 'var(--primary)' }}>Running eligibility policy engine...</div>
              <div style={{ marginBottom: '1rem', color: 'var(--primary)' }}>Retrieving policy context details...</div>
            </div>
          ) : assessmentResult && (
            <div className="animate-fade-in">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <VerdictMetric 
                  label="Decision" 
                  value={assessmentResult.decision} 
                  type={assessmentResult.decision === 'Eligible' ? 'success' : assessmentResult.decision === 'Conditionally Eligible' ? 'warning' : 'danger'} 
                />
                <VerdictMetric 
                  label="Confidence" 
                  value={assessmentResult.confidence} 
                  type="warning" 
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ color: 'var(--primary)', marginBottom: '0.5rem' }}>AI Underwriter Report</h4>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', fontSize: '0.95rem' }}>
                  <div dangerouslySetInnerHTML={{ __html: assessmentResult.reasoning.replace(/\n/g, '<br/>') }} />
                </div>
              </div>

              {assessmentResult.documents_required?.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ marginBottom: '0.5rem' }}>Required Documents</h4>
                  <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    {assessmentResult.documents_required.map((doc: string, i: number) => (
                      <li key={i}>{doc}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', gap: '0.5rem', alignItems: 'flex-start', background: 'rgba(255,106,0,0.05)', padding: '0.75rem', borderRadius: '8px' }}>
                <ShieldAlert size={16} color="var(--primary)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <span>This application operates under Databricks Unity Catalog governance. All agent decisions are logged for compliance auditing. Outputs are generated by AI and may be subject to final human review.</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function VerdictMetric({ label, value, type }: { label: string, value: string, type: 'success'|'warning'|'danger' }) {
  const color = type === 'success' ? 'var(--accent-success)' : type === 'warning' ? 'var(--accent-warning)' : 'var(--accent-danger)';
  const Icon = type === 'success' ? CheckCircle : type === 'warning' ? AlertTriangle : XCircle;
  
  return (
    <div style={{ textAlign: 'center', background: `${color}15`, border: `1px solid ${color}`, borderRadius: '12px', padding: '1rem' }}>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{label}</div>
      <div style={{ color, fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
        <Icon size={20} />
        {value}
      </div>
    </div>
  );
}
