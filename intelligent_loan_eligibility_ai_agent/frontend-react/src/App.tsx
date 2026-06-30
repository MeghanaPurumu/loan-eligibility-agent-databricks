import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Settings, Users, FileText, MessageSquare, BarChart2 } from 'lucide-react';
import './index.css';

// Components
import AssessmentWorkspace from './pages/AssessmentWorkspace';
import ConversationalFollowUp from './pages/ConversationalFollowUp';
import AnalyticsDashboard from './pages/AnalyticsDashboard';

const API_BASE_URL = 'http://localhost:8000/api';

function App() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<any>(null);
  
  // Shared state that was in Streamlit session_state
  const [activePayload, setActivePayload] = useState<any>({});
  const [assessmentResult, setAssessmentResult] = useState<any>(null);
  const [hasAssessed, setHasAssessed] = useState(false);
  const [chatHistory, setChatHistory] = useState<any[]>([]);

  useEffect(() => {
    // Fetch customers on load
    axios.get(`${API_BASE_URL}/customers`)
      .then(res => setCustomers(res.data))
      .catch(err => console.error("Error fetching customers:", err));
  }, []);

  const handleCustomerSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const name = e.target.value;
    if (name === '-- New Applicant --') {
      setSelectedCustomer(null);
      resetSession();
      return;
    }
    
    const customer = customers.find(c => c.name === name);
    if (customer) {
      setSelectedCustomer(customer);
      // Initialize active payload with customer data
      const payload = {
        name: customer.name,
        age: parseInt(customer.age),
        monthly_income: parseInt(customer.monthly_income),
        employment_type: customer.employment_type,
        credit_score: parseInt(customer.credit_score),
        monthly_loan_payment: parseInt(customer.existing_liabilities),
        existing_loan: parseInt(customer.existing_liabilities) > 0 ? "Yes" : "No",
        loan_amount_requested: parseInt(customer.loan_amount_requested),
        loan_purpose: "General Purchase"
      };
      setActivePayload(payload);
      setAssessmentResult(null);
      setHasAssessed(false);
      setChatHistory([]);
    }
  };

  const resetSession = () => {
    setSelectedCustomer(null);
    setActivePayload({});
    setAssessmentResult(null);
    setHasAssessed(false);
    setChatHistory([]);
  };

  return (
    <Router>
      <div className="app-container">
        {/* Sidebar */}
        <aside className="sidebar">
          <div>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <Settings size={24} color="var(--primary)" />
              Settings
            </h2>
            <div style={{ padding: '0.75rem', background: 'rgba(52, 152, 219, 0.1)', color: '#3498db', borderRadius: '8px', fontSize: '0.875rem' }}>
              Banking Agent Control Panel
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <NavLink to="/" className={({isActive}) => `btn btn-secondary ${isActive ? 'active' : ''}`} style={{justifyContent: 'flex-start'}}>
              <FileText size={18} /> Assessment Workspace
            </NavLink>
            <NavLink to="/chat" className={({isActive}) => `btn btn-secondary ${isActive ? 'active' : ''}`} style={{justifyContent: 'flex-start'}}>
              <MessageSquare size={18} /> Conversational Follow-up
            </NavLink>
            <NavLink to="/dashboard" className={({isActive}) => `btn btn-secondary ${isActive ? 'active' : ''}`} style={{justifyContent: 'flex-start'}}>
              <BarChart2 size={18} /> Analytics Dashboard
            </NavLink>
          </div>
          
          <hr style={{ borderColor: 'var(--border-color)', margin: '1rem 0' }} />

          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', fontSize: '1.1rem' }}>
              <Users size={20} />
              Customer Directory
            </h3>
            <div className="input-group">
              <label>Select Existing Applicant</label>
              <select className="select" onChange={handleCustomerSelect} value={selectedCustomer?.name || '-- New Applicant --'}>
                <option value="-- New Applicant --">-- New Applicant --</option>
                {customers.map((c, i) => (
                  <option key={i} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          <hr style={{ borderColor: 'var(--border-color)', margin: '1rem 0' }} />
          
          <button className="btn btn-secondary" onClick={resetSession} style={{ width: '100%' }}>
            Reset Assessment Session
          </button>
          
          <div style={{ marginTop: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
            v2.0 | Mode: LOCAL | Provider: OLLAMA
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={
              <AssessmentWorkspace 
                activePayload={activePayload}
                setActivePayload={setActivePayload}
                assessmentResult={assessmentResult}
                setAssessmentResult={setAssessmentResult}
                hasAssessed={hasAssessed}
                setHasAssessed={setHasAssessed}
                setChatHistory={setChatHistory}
                API_BASE_URL={API_BASE_URL}
              />
            } />
            <Route path="/chat" element={
              <ConversationalFollowUp 
                activePayload={activePayload}
                assessmentResult={assessmentResult}
                chatHistory={chatHistory}
                setChatHistory={setChatHistory}
                API_BASE_URL={API_BASE_URL}
              />
            } />
            <Route path="/dashboard" element={
              <AnalyticsDashboard API_BASE_URL={API_BASE_URL} />
            } />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
