import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, User, Bot } from 'lucide-react';

export default function ConversationalFollowUp({ activePayload, assessmentResult, chatHistory, setChatHistory, API_BASE_URL }: any) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading]);

  if (!assessmentResult) {
    return (
      <div className="animate-fade-in" style={{ textAlign: 'center', padding: '4rem 2rem', color: 'var(--text-muted)' }}>
        <h2 style={{ marginBottom: '1rem', color: 'var(--text-main)' }}>No Active Assessment</h2>
        <p>Please run an assessment first in the Assessment Workspace to discuss the results.</p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userMessage = { role: 'user', content: query };
    const newHistory = [...chatHistory, userMessage];
    setChatHistory(newHistory);
    setQuery('');
    setLoading(true);

    try {
      const res = await axios.post(`${API_BASE_URL}/chat`, {
        query: userMessage.content,
        payload: activePayload,
        result: assessmentResult,
        history: chatHistory // send previous history
      });
      
      setChatHistory([...newHistory, { role: 'assistant', content: res.data.response }]);
    } catch (err) {
      console.error("Chat error:", err);
      setChatHistory([...newHistory, { role: 'assistant', content: 'Sorry, there was an error processing your request.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
      <div className="hero" style={{ marginBottom: '1rem' }}>
        <h2>Conversational Follow-up</h2>
        <p>Review the assessment and ask follow-up questions (e.g. "Why was I rejected?" or "What should I improve?"):</p>
      </div>

      <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {chatHistory.length === 0 && (
            <div style={{ textAlign: 'center', margin: 'auto', color: 'var(--text-muted)' }}>
              Ask your first question to the Intelligent Loan Assistant...
            </div>
          )}
          
          {chatHistory.map((msg: any, i: number) => (
            <div key={i} style={{ 
              display: 'flex', 
              gap: '1rem', 
              alignItems: 'flex-start',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row'
            }}>
              <div style={{ 
                width: 36, height: 36, borderRadius: '50%', 
                background: msg.role === 'user' ? 'var(--primary)' : '#2a3441',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
              }}>
                {msg.role === 'user' ? <User size={20} color="#fff" /> : <Bot size={20} color="#fff" />}
              </div>
              <div style={{ 
                background: msg.role === 'user' ? 'rgba(255,106,0,0.1)' : 'rgba(255,255,255,0.03)',
                padding: '1rem', borderRadius: '12px',
                border: `1px solid ${msg.role === 'user' ? 'rgba(255,106,0,0.2)' : 'var(--border-color)'}`,
                maxWidth: '80%'
              }}>
                <div dangerouslySetInnerHTML={{ __html: msg.content.replace(/\n/g, '<br/>') }} />
              </div>
            </div>
          ))}
          
          {loading && (
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#2a3441', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Bot size={20} color="#fff" />
              </div>
              <div style={{ padding: '1rem', color: 'var(--text-muted)' }}>
                Analyzing credit context...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1rem', borderTop: '1px solid var(--border-color)', display: 'flex', gap: '0.5rem', background: 'rgba(0,0,0,0.2)' }}>
          <input 
            type="text" 
            className="input" 
            placeholder="Type your question here..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, marginBottom: 0 }}
            disabled={loading}
          />
          <button type="submit" className="btn" disabled={loading || !query.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
