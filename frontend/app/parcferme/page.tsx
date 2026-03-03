"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, BrainCircuit, Table as TableIcon, Activity, Map as MapIcon, ChevronRight } from "lucide-react";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

/* ═══════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════ */
interface Visualization {
    type: "chart" | "map";
    component: string;
    chart_data?: any;
    geo_json?: any;
    options?: any;
}
interface TableData {
    title: string;
    headers: string[];
    rows: string[][];
}
interface ChatResponse {
    text_response: string;
    metadata: { timestamp: string; session: string; entities: string[] };
    visualizations?: Visualization[];
    tables?: TableData[];
}
interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    data?: ChatResponse;
}

/* ═══════════════════════════════════════════════════════════════════════
   ENTITY LINKING (Asset Resolver)
   ═══════════════════════════════════════════════════════════════════════ */
const resolveEntityImage = (entityId: string): string => {
    const map: Record<string, string> = {
        "DRV_HAM": "/assets/Teams/Ferrari/2025ferrarilewham01right.avif",
        "DRV_RUS": "/assets/Teams/Mercedes/2025mercedesgeorus01right.avif",
        "DRV_VER": "/assets/Teams/Red Bull Racing/2025redbullracingmaxver01right.avif",
        "DRV_NOR": "/assets/Teams/McLaren/2025mclarenlannor01right.avif",
        "DRV_LEC": "/assets/Teams/Ferrari/2025ferrarichalec01right.avif",
        "DRV_SAI": "/assets/Teams/Williams/2025williamscarsai01right.avif",
        "DRV_PIA": "/assets/Teams/McLaren/2025mclarenoscpia01right.avif",
        "DRV_ALO": "/assets/Teams/Aston Martin/2025astonmartinferalo01right.avif"
    };
    return map[entityId] || "";
};

/* ═══════════════════════════════════════════════════════════════════════
   SUGGESTED PROMPTS
   ═══════════════════════════════════════════════════════════════════════ */
const SUGGESTIONS = [
    "Compare Verstappen vs Norris",
    "How does the model work?",
    "Who won the 2022 season?",
    "Show me the 2026 driver lineup",
    "What are the 2026 regulations?",
    "Tell me about Leclerc",
    "Show tire degradation analysis",
    "Speed trace at Turn 1",
];

/* ═══════════════════════════════════════════════════════════════════════
   PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════════════ */
export default function ParcFermePage() {
    const [messages, setMessages] = useState<Message[]>([{
        id: "sys_1",
        role: "assistant",
        content: "Welcome to ParcFermé! I've been upgraded to a memory-enabled Agentic RAG system Powered by LangGraph and Groq LLM. I can understand context across multiple messages, analyze dynamic live telemetry, compare drivers meaningfully, and provide up-to-date F1 intel on the 2026 season — including regulations, driver lineups, and circuits.\n\nTry asking me anything below!"
    }]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };
    useEffect(() => { scrollToBottom(); }, [messages, isLoading]);

    const sendMessage = async (text: string) => {
        if (!text.trim() || isLoading) return;
        setInput("");
        setMessages(prev => [...prev, { id: Date.now().toString(), role: "user", content: text.trim() }]);
        setIsLoading(true);

        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${baseUrl}/api/v1/chat`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text.trim() })
            });

            if (!res.ok) {
                const text = await res.text();
                throw new Error(`HTTP error! status: ${res.status}, body: ${text.substring(0, 100)}`);
            }

            const data: ChatResponse = await res.json();
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: data.text_response,
                data: data
            }]);
        } catch (error: any) {
            console.error("Chat error:", error);
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `⚠️ Telemetry connection failed! Attempted to reach backend at: ${baseUrl}. Error details: ${error.message || error}`
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        sendMessage(input);
    };

    /* ── Render: Visualizations ────────────────────────────────────────── */
    const renderVisualizations = (visList: Visualization[]) => {
        return visList.map((vis, idx) => {
            if (vis.type === "chart" && vis.chart_data) {
                const chartOptions = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: 'rgba(255, 255, 255, 0.7)', font: { size: 11 } } },
                        title: { display: true, text: vis.options?.title || "", color: 'white', font: { size: 14 } }
                    },
                    scales: {
                        y: { grid: { color: 'rgba(255,255,255,0.08)' }, ticks: { color: 'rgba(255,255,255,0.5)' } },
                        x: { grid: { color: 'rgba(255,255,255,0.08)' }, ticks: { color: 'rgba(255,255,255,0.5)' } }
                    }
                };

                return (
                    <div key={idx} className="mt-4 p-4 rounded-xl bg-black/40 border border-white/10 w-full" style={{ height: 280 }}>
                        <div className="flex items-center gap-2 mb-2 text-f1-muted text-[10px] uppercase tracking-widest">
                            <Activity className="w-3 h-3" /> Telemetry Data Orchestrator
                        </div>
                        {vis.component === "LineChart" ? (
                            <Line data={vis.chart_data} options={chartOptions} />
                        ) : (
                            <Bar data={vis.chart_data} options={chartOptions} />
                        )}
                    </div>
                );
            }

            if (vis.type === "map" && vis.geo_json) {
                return (
                    <div key={idx} className="mt-4 p-4 rounded-xl bg-black/40 border border-white/10 w-full relative overflow-hidden" style={{ height: 280 }}>
                        <div className="absolute top-4 left-4 flex items-center gap-2 text-f1-muted text-[10px] uppercase tracking-widest z-10">
                            <MapIcon className="w-3 h-3" /> Geospatial Track Map Engine
                        </div>
                        <svg viewBox="0 0 400 260" className="w-full h-full opacity-30 stroke-f1-muted stroke-[3] fill-transparent absolute inset-0">
                            <path d="M 50,220 C 50,40 350,40 350,220" />
                        </svg>
                        <div className="relative z-10 flex items-center justify-center gap-16 h-full pt-6">
                            {vis.geo_json.features.map((feat: any, nodeIdx: number) => {
                                const driverImg = resolveEntityImage(feat.properties.id);
                                return (
                                    <div key={nodeIdx} className="flex flex-col items-center gap-2">
                                        <div className={`w-14 h-14 rounded-full overflow-hidden border-2 shadow-lg ${nodeIdx === 0 ? "border-red-500 shadow-red-500/30" : "border-teal-500 shadow-teal-500/30"}`}>
                                            {driverImg ? <img src={driverImg} alt={feat.properties.label} className="w-full h-full object-cover object-top" /> : <div className="w-full h-full bg-white/20 flex items-center justify-center text-xl">🏎️</div>}
                                        </div>
                                        <span className="text-sm font-black text-white">{feat.properties.label}</span>
                                        <span className="text-xs font-mono text-white/70">{feat.properties.speed} kph</span>
                                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${feat.properties.active_aero === "X-Mode" ? "bg-red-500/20 text-red-400 border border-red-500/30" : "bg-teal-500/20 text-teal-400 border border-teal-500/30"}`}>
                                            {feat.properties.active_aero}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                );
            }
            return null;
        });
    };

    /* ── Render: Tables ────────────────────────────────────────────────── */
    const renderTables = (tables: TableData[]) => {
        return tables.map((tb, idx) => (
            <div key={idx} className="mt-4 rounded-xl bg-black/40 border border-white/10 w-full overflow-x-auto">
                <div className="flex items-center gap-2 px-4 py-3 text-f1-muted text-[10px] uppercase tracking-widest border-b border-white/10">
                    <TableIcon className="w-3 h-3" /> {tb.title}
                </div>
                <table className="w-full text-sm text-left">
                    <thead>
                        <tr className="bg-white/5">
                            {tb.headers.map((h, i) => <th key={i} className="px-4 py-2.5 text-xs font-black text-white uppercase tracking-wider">{h}</th>)}
                        </tr>
                    </thead>
                    <tbody>
                        {tb.rows.map((row, i) => (
                            <tr key={i} className="border-t border-white/5 hover:bg-white/5 transition-colors">
                                {row.map((cell, j) => (
                                    <td key={j} className={`px-4 py-2.5 ${j === 0 ? 'font-bold text-white' : 'text-white/70 font-mono text-xs'}`}>
                                        {cell}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        ));
    };

    /* ── Render: Entity Badges ─────────────────────────────────────────── */
    const renderEntities = (entities: string[]) => {
        if (!entities || entities.length === 0) return null;
        return (
            <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-white/10">
                <span className="text-[10px] text-f1-muted uppercase self-center mr-1">Entities:</span>
                {entities.map(id => {
                    const img = resolveEntityImage(id);
                    return (
                        <div key={id} className="flex items-center gap-1.5 bg-white/5 border border-white/10 rounded-full py-0.5 px-2.5">
                            {img && <img src={img} alt={id} className="w-4 h-4 rounded-full object-cover object-top" />}
                            <span className="text-[11px] font-mono text-white/60">{id.replace(/(DRV_|TRK_)/g, '')}</span>
                        </div>
                    );
                })}
            </div>
        );
    };

    /* ═══════════════════════════════════════════════════════════════════════
       RENDER
       ═══════════════════════════════════════════════════════════════════════ */
    return (
        <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full mb-20 animate-in fade-in duration-700">
            {/* Header */}
            <div className="flex flex-col gap-2">
                <h1 className="text-4xl md:text-5xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-emerald-500 italic" style={{ fontFamily: 'Magneto, cursive, sans-serif' }}>
                    ParcFermé AI
                </h1>
                <p className="text-f1-muted text-lg tracking-wider font-semibold flex items-center gap-2">
                    <BrainCircuit className="w-5 h-5" /> Autonomous Strategic Intelligence Engine
                </p>
            </div>

            {/* Suggestion Chips */}
            {messages.length <= 1 && (
                <div className="flex flex-wrap gap-2">
                    {SUGGESTIONS.map((s) => (
                        <button key={s} onClick={() => sendMessage(s)}
                            className="px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-white/70 hover:bg-white/10 hover:text-white hover:border-white/20 transition-all">
                            {s}
                        </button>
                    ))}
                </div>
            )}

            {/* Messages */}
            <div className="flex flex-col gap-6">
                {messages.map((msg) => (
                    <div key={msg.id} className={`flex gap-4 ${msg.role === "user" ? "justify-end" : ""}`}>
                        {/* Avatar (assistant only, left side) */}
                        {msg.role === "assistant" && (
                            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border bg-teal-500/20 border-teal-500/50 text-teal-400 self-start mt-1">
                                <Bot className="w-5 h-5" />
                            </div>
                        )}

                        {/* Content */}
                        <div className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end max-w-[70%]" : "items-start max-w-[85%]"} min-w-0`}>
                            {/* Session Badge */}
                            {msg.role === "assistant" && msg.data?.metadata && (
                                <div className="text-[10px] text-f1-muted font-mono uppercase tracking-wider flex items-center gap-2 mb-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse" />
                                    <span>{msg.data.metadata.session}</span>
                                </div>
                            )}

                            <div className={`p-4 rounded-2xl text-sm leading-relaxed w-full ${msg.role === "user"
                                ? "bg-gradient-to-br from-white/15 to-white/5 text-white border border-white/20 font-medium"
                                : "bg-white/[0.03] border border-white/10 text-white/90"
                                }`}>
                                {/* Text */}
                                <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{
                                    __html: msg.content
                                        .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
                                        .replace(/\n/g, '<br/>')
                                }} />

                                {/* Dynamic JSON Renderers */}
                                {msg.data?.visualizations && msg.data.visualizations.length > 0 && renderVisualizations(msg.data.visualizations)}
                                {msg.data?.tables && msg.data.tables.length > 0 && renderTables(msg.data.tables)}
                                {msg.data?.metadata?.entities && msg.data.metadata.entities.length > 0 && renderEntities(msg.data.metadata.entities)}
                            </div>
                        </div>

                        {/* Avatar (user only, right side) */}
                        {msg.role === "user" && (
                            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border bg-white/10 border-white/20 text-white self-start mt-1">
                                <User className="w-5 h-5" />
                            </div>
                        )}
                    </div>
                ))}

                {/* Loading */}
                {isLoading && (
                    <div className="flex gap-4">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border bg-teal-500/20 border-teal-500/50 text-teal-400">
                            <Bot className="w-5 h-5 animate-pulse" />
                        </div>
                        <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/10 flex items-center gap-3">
                            <div className="flex gap-1">
                                <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                <div className="w-2 h-2 bg-teal-500 rounded-full animate-bounce"></div>
                            </div>
                            <span className="text-xs text-f1-muted uppercase tracking-wider">Parsing Telemetry Streams...</span>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input — Normal flow, scrolls with page */}
            <form onSubmit={handleSubmit} className="sticky bottom-4 z-30">
                <div className="glass-card rounded-2xl p-2 flex items-center border border-white/20 hover:border-white/40 transition-colors bg-f1-dark/95 backdrop-blur-xl shadow-2xl shadow-black/50">
                    <ChevronRight className="w-5 h-5 text-teal-500 ml-3 shrink-0" />
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask ParcFermé about F1 data, driver stats, model architecture, regulations..."
                        className="flex-1 bg-transparent border-none text-white focus:ring-0 placeholder-white/30 text-sm px-3 py-3 outline-none"
                    />
                    <button
                        type="submit"
                        disabled={isLoading || !input.trim()}
                        className="bg-teal-500 text-black p-2.5 rounded-xl hover:bg-teal-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0 font-bold"
                    >
                        <Send className="w-4 h-4" />
                    </button>
                </div>
            </form>
        </div>
    );
}
