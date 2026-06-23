import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { FileUp, Link, MessageSquareText, RefreshCw, Send, Server } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

function App() {
  const [reportUrl, setReportUrl] = useState("");
  const [file, setFile] = useState(null);
  const [state, setState] = useState({});
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("No document uploaded");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [chatBusy, setChatBusy] = useState(false);
  const chatEndRef = useRef(null);

  const ready = useMemo(() => {
    const status = state?.status || state?.state?.status;
    return ["done", "noop", "self_managed"].includes(status);
  }, [state]);

  useEffect(() => {
    refreshHealth();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const text = await response.text();
    const body = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
    }
    return body;
  }

  async function refreshHealth() {
    try {
      const result = await request("/api/health");
      setState(result.state || {});
      setStatusText(result.state?.status ? `Document status: ${result.state.status}` : "No document uploaded");
    } catch (error) {
      setStatusText(`Backend unavailable: ${error.message}`);
    }
  }

  async function refreshStatus() {
    setBusy(true);
    try {
      const result = await request("/api/status");
      setState((previous) => ({ ...previous, status: result.process_status, status_detail: result }));
      setStatusText(`Document status: ${result.process_status || result.status}`);
    } catch (error) {
      setStatusText(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function ingestUrl() {
    setBusy(true);
    setStatusText("Uploading URL to Mistral and waiting for processing...");
    try {
      const result = await request("/api/ingest/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: reportUrl || null, wait: true }),
      });
      setState(result);
      setStatusText(`Ready: ${result.status}`);
    } catch (error) {
      setStatusText(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function ingestFile() {
    if (!file) return;
    setBusy(true);
    setStatusText("Uploading PDF to Mistral and waiting for processing...");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await request("/api/ingest/upload?wait=true", { method: "POST", body: form });
      setState(result);
      setStatusText(`Ready: ${result.status}`);
    } catch (error) {
      setStatusText(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function askQuestion(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || chatBusy) return;
    const visibleHistory = [...messages, { role: "user", content: trimmed }];
    setMessages(visibleHistory);
    setQuestion("");
    setChatBusy(true);
    try {
      const history = messages.filter((message) => ["user", "assistant"].includes(message.role));
      const result = await request("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed, history }),
      });
      setMessages([...visibleHistory, { role: "assistant", content: result.answer || "No answer returned." }]);
    } catch (error) {
      setMessages([...visibleHistory, { role: "assistant", content: `Error: ${error.message}` }]);
    } finally {
      setChatBusy(false);
    }
  }

  return (
    <main className="shell">
      <section className="workspace">
        <aside className="sidebar">
          <div className="brand">
            <Server size={22} />
            <div>
              <h1>Mistral RAG</h1>
              <p>Halfords annual report workspace</p>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">
              <Link size={18} />
              <h2>Report URL</h2>
            </div>
            <input
              value={reportUrl}
              onChange={(event) => setReportUrl(event.target.value)}
              placeholder="https://.../annual-report-2025.pdf"
            />
            <button onClick={ingestUrl} disabled={busy}>
              <Link size={17} />
              Ingest URL
            </button>
          </div>

          <div className="panel">
            <div className="panel-title">
              <FileUp size={18} />
              <h2>Local PDF</h2>
            </div>
            <input type="file" accept=".pdf,.txt,.docx" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            <button onClick={ingestFile} disabled={busy || !file}>
              <FileUp size={17} />
              Upload File
            </button>
          </div>

          <div className="status">
            <button className="icon-button" onClick={refreshStatus} disabled={busy} title="Refresh processing status">
              <RefreshCw size={17} />
            </button>
            <span>{busy ? "Working..." : statusText}</span>
          </div>

          <div className="meta">
            <span>Library</span>
            <code>{state.library_id || state.state?.library_id || "not created"}</code>
            <span>Document</span>
            <code>{state.document_id || state.state?.document_id || "not uploaded"}</code>
          </div>
        </aside>

        <section className="chat">
          <header className="chat-header">
            <div>
              <h2>Ask the Report</h2>
              <p>{ready ? "Retrieval is ready." : "Upload and process a document before asking questions."}</p>
            </div>
            <MessageSquareText size={24} />
          </header>

          <div className="messages">
            {messages.length === 0 && (
              <div className="empty">
                <p>Try: What were the key financial results in FY25?</p>
                <p>Try: Summarize the main risks and strategy updates.</p>
              </div>
            )}
            {messages.map((message, index) => (
              <article className={`bubble ${message.role}`} key={`${message.role}-${index}`}>
                <span>{message.role === "user" ? "You" : "Mistral"}</span>
                <p>{message.content}</p>
              </article>
            ))}
            {chatBusy && <article className="bubble assistant"><span>Mistral</span><p>Thinking with the document library...</p></article>}
            <div ref={chatEndRef} />
          </div>

          <form className="composer" onSubmit={askQuestion}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about the uploaded annual report"
            />
            <button disabled={!question.trim() || chatBusy}>
              <Send size={18} />
              Send
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
