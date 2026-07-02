import { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { ShieldCheck, ShieldAlert, Clock } from 'lucide-react';

export default function AnalyticsDashboard({ API_BASE_URL }: { API_BASE_URL: string }) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/dashboard`)
      .then(res => {
        let logs = res.data.data;
        if (!logs || logs.length === 0) {
          // Fallback mock data
          logs = [
            {decision: "Eligible", guardrail_status: "Compliant", latency: 1.2},
            {decision: "Eligible", guardrail_status: "Compliant", latency: 1.5},
            {decision: "Conditionally Eligible", guardrail_status: "Compliant", latency: 1.9},
            {decision: "Not Eligible", guardrail_status: "Compliant", latency: 0.8},
            {decision: "Not Eligible", guardrail_status: "Blocked (Input Guardrail)", latency: 0.2},
            {decision: "Eligible", guardrail_status: "Compliant", latency: 2.1},
            {decision: "Not Eligible", guardrail_status: "Compliant", latency: 1.1},
            {decision: "Conditionally Eligible", guardrail_status: "Compliant", latency: 1.7},
            {decision: "Eligible", guardrail_status: "Compliant", latency: 1.3},
            {decision: "Not Eligible", guardrail_status: "Blocked (Input Guardrail)", latency: 0.15},
          ];
        }
        setData(logs);
        setLoading(false);
      })
      .catch(err => {
        console.error("Dashboard error:", err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ padding: '2rem' }}>Loading dashboard...</div>;

  const totalApps = data.length;
  const eligibleCount = data.filter(d => d.decision === 'Eligible').length;
  const condCount = data.filter(d => d.decision === 'Conditionally Eligible').length;
  const notEligibleCount = data.filter(d => d.decision === 'Not Eligible').length;
  const approvalRate = totalApps > 0 ? Math.round((eligibleCount / totalApps) * 100) : 0;
  
  const violationsCount = data.filter(d => d.guardrail_status?.includes('Blocked') || d.guardrail_status?.includes('Violation')).length;
  const avgLatency = totalApps > 0 ? (data.reduce((acc, curr) => acc + (curr.latency || 0), 0) / totalApps).toFixed(2) : "0.00";

  const decisionChartData = [
    { name: 'Eligible', count: eligibleCount },
    { name: 'Conditionally', count: condCount },
    { name: 'Not Eligible', count: notEligibleCount },
  ];

  return (
    <div className="animate-fade-in">
      <div className="hero" style={{ marginBottom: '2rem' }}>
        <h2>Assessment Analytics Dashboard</h2>
        <p>Real-time metrics on underwriting decisions and system performance.</p>
      </div>

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <MetricCard label="Total Applications" value={totalApps.toString()} color="#ff6a00" />
        <MetricCard label="Approval Rate" value={`${approvalRate}%`} color="#e67e22" />
        <MetricCard label="Guardrail Violations" value={violationsCount.toString()} color={violationsCount > 0 ? '#c0392b' : '#ff9a44'} />
        <MetricCard label="Avg Latency" value={`${avgLatency}s`} color="#e67e22" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Loan Decision Distribution</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={decisionChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <RechartsTooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{background: '#151a28', border: '1px solid #2a3441', borderRadius: '8px'}} />
                <Bar dataKey="count" fill="#ff6a00" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Guardrail Compliance</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', height: '100%', alignItems: 'center' }}>
             <div style={{ textAlign: 'center', padding: '1.5rem 1rem', background: 'rgba(255,106,0,0.1)', borderRadius: '12px' }}>
                <ShieldCheck size={32} color="#ff6a00" style={{ margin: '0 auto 0.5rem' }} />
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#ff6a00' }}>{totalApps - violationsCount}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Compliant</div>
             </div>
             <div style={{ textAlign: 'center', padding: '1.5rem 1rem', background: 'rgba(192,57,43,0.1)', borderRadius: '12px' }}>
                <ShieldAlert size={32} color="#c0392b" style={{ margin: '0 auto 0.5rem' }} />
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#c0392b' }}>{violationsCount}</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Blocked</div>
             </div>
             <div style={{ textAlign: 'center', padding: '1.5rem 1rem', background: 'rgba(230,126,34,0.1)', borderRadius: '12px' }}>
                <Clock size={32} color="#e67e22" style={{ margin: '0 auto 0.5rem' }} />
                <div style={{ fontSize: '2rem', fontWeight: 700, color: '#e67e22' }}>{avgLatency}s</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Avg Processing</div>
             </div>
          </div>
        </div>
      </div>
      
      <div className="card">
        <h3 style={{ marginBottom: '1rem' }}>Recent Assessment Transactions</h3>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '0.75rem' }}>Decision</th>
                <th style={{ padding: '0.75rem' }}>Guardrail Status</th>
                <th style={{ padding: '0.75rem' }}>Latency (s)</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(-10).map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '0.75rem' }}>
                    <span style={{ 
                      padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.85rem',
                      background: row.decision === 'Eligible' ? 'rgba(46,204,113,0.1)' : row.decision === 'Conditionally Eligible' ? 'rgba(241,196,15,0.1)' : 'rgba(231,76,60,0.1)',
                      color: row.decision === 'Eligible' ? '#2ecc71' : row.decision === 'Conditionally Eligible' ? '#f1c40f' : '#e74c3c'
                    }}>
                      {row.decision}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem' }}>{row.guardrail_status}</td>
                  <td style={{ padding: '0.75rem' }}>{row.latency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string, value: string, color: string }) {
  return (
    <div style={{ textAlign: 'center', background: `${color}15`, border: `1px solid ${color}`, borderRadius: '12px', padding: '1.5rem' }}>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{label}</div>
      <div style={{ fontSize: '2rem', fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
