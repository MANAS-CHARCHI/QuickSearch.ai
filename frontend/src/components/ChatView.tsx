import React, { useState, useRef, useEffect } from "react";
import { Sparkles, ArrowUp, ShieldCheck } from "lucide-react";
import { ChatMessage } from "../types";

interface ChatViewProps {
  messages: ChatMessage[];
  onSendMessage: (query: string) => void;
  isLoading: boolean;
}

export const ChatView: React.FC<ChatViewProps> = ({
  messages,
  onSendMessage,
  isLoading,
}) => {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickPrompts = [
    { label: "Aadhaar UID & address", query: "Give me my Aadhaar number and registered address" },
    { label: "Passport expiry date", query: "When does my passport expire?" },
    { label: "Blood sugar & lipid panel", query: "What are my fasting blood sugar and cholesterol levels?" },
    { label: "Tax return & refund", query: "What was my gross income, deductions, and tax refund?" },
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput("");
  };

  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col h-full sm:h-[calc(100vh-160px)] sm:max-h-[600px] sm:min-h-[440px] bg-[#FFFCF9] sm:bg-white dark:bg-[#140E0A] sm:dark:bg-[#1C1510] border-0 sm:border border-orange-200/80 dark:border-[#2D2118] rounded-none sm:rounded-2xl shadow-none sm:shadow-val overflow-hidden transition-all">
      {/* Desktop Assistant Top Bar */}
      <div className="hidden sm:flex shrink-0 px-4 py-2.5 border-b border-orange-200/60 dark:border-[#2D2118] items-center justify-between bg-orange-50/60 dark:bg-[#221913] font-sans">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded bg-orange-600 flex items-center justify-center text-white text-[9px] font-bold font-mono">
            vc
          </div>
          <span className="text-xs font-semibold text-stone-900 dark:text-white">
            Vault Assistant
          </span>
          <span className="text-[10px] text-stone-400">•</span>
          <span className="text-xs text-stone-500 dark:text-stone-400">
            Semantic search across your encrypted records
          </span>
        </div>

        <div className="flex items-center space-x-1.5 text-[11px] text-stone-400 font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
          <span>zero-knowledge RAG</span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-5 space-y-3.5 font-sans min-h-0">
        {/* If no messages yet, show hero greeting */}
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 max-w-sm mx-auto my-auto">
            <div className="w-12 h-12 rounded-2xl bg-orange-600 flex items-center justify-center text-white font-bold text-xl shadow-sm mb-3">
              vc
            </div>
            <h2 className="text-base sm:text-lg font-bold text-stone-900 dark:text-white">
              Vault Assistant
            </h2>
            <p className="text-xs text-stone-500 dark:text-stone-400 mt-1 leading-relaxed">
              Ask questions about your uploaded documents, personal IDs, health lab panels, or taxes.
            </p>
            <div className="grid grid-cols-1 gap-2 w-full mt-5 text-left">
              {quickPrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(p.query)}
                  className="p-2.5 rounded-xl bg-white dark:bg-[#1C1510] border border-orange-200/80 dark:border-[#2D2118] hover:border-orange-400 dark:hover:border-orange-500/50 transition-all text-xs text-stone-700 dark:text-stone-300 shadow-xs flex items-center justify-between group cursor-pointer"
                >
                  <span className="font-medium text-[11px] truncate">{p.label}</span>
                  <ArrowUp className="w-3 h-3 text-stone-400 group-hover:text-orange-600 rotate-45 shrink-0 ml-1 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message Bubble Feed */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.sender === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-[88%] sm:max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs sm:text-[13px] leading-relaxed transition-all shadow-xs ${
                msg.sender === "user"
                  ? "bg-stone-900 text-white dark:bg-[#FAF5F0] dark:text-stone-950 rounded-br-xs font-normal"
                  : "bg-white dark:bg-[#1C1510] text-stone-900 dark:text-stone-100 border border-orange-200/80 dark:border-[#2D2118] rounded-tl-xs"
              }`}
            >
              {msg.sender === "assistant" && (
                <div className="flex items-center space-x-1.5 mb-1.5 pb-1 border-b border-orange-100/80 dark:border-[#281D15]">
                  <div className="w-3.5 h-3.5 rounded bg-orange-600 flex items-center justify-center text-white text-[8px] font-bold font-mono">
                    vc
                  </div>
                  <span className="text-[10px] font-semibold text-stone-700 dark:text-stone-300">
                    Vault Assistant
                  </span>
                  <span className="text-[9px] text-emerald-600 dark:text-emerald-400 font-mono">
                    • RAG match
                  </span>
                </div>
              )}

              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Source references */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2.5 pt-1.5 border-t border-orange-100 dark:border-[#281D15] flex items-center flex-wrap gap-1 font-mono">
                  <span className="text-[9px] text-stone-400">sources:</span>
                  {msg.sources.map((src, idx) => (
                    <span
                      key={idx}
                      className="text-[9px] bg-orange-500/10 text-orange-700 dark:text-orange-400 px-1.5 py-0.5 rounded border border-orange-500/20 font-medium"
                    >
                      @{src}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 text-xs text-stone-600 dark:text-stone-400 bg-white dark:bg-[#1C1510] px-3.5 py-2 rounded-xl border border-orange-200/80 dark:border-[#2D2118] w-fit shadow-xs">
            <span className="flex space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
            <span className="text-[11px] font-mono">Searching secure documents...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat Write — Positioned at the very bottom in a modern chatbot way */}
      <div className="shrink-0 bg-[#FFFCF9]/95 sm:bg-white dark:bg-[#140E0A]/95 sm:dark:bg-[#1C1510] border-t border-orange-200/70 dark:border-[#2D2118] p-2.5 sm:p-3 pb-[max(0.75rem,env(safe-area-inset-bottom,0px))] sm:pb-3">
        {/* Suggestion Chips strip above input */}
        {messages.length > 0 && messages.length <= 4 && (
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-2 px-0.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => onSendMessage(p.query)}
                className="text-[11px] whitespace-nowrap bg-white dark:bg-[#1C1510] hover:bg-orange-50 dark:hover:bg-[#251A12] border border-orange-200/80 dark:border-[#2D2118] text-stone-700 dark:text-stone-300 px-2.5 py-1 rounded-full transition-all cursor-pointer font-sans shrink-0 shadow-xs active:scale-95"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {/* Input Form Pill */}
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your documents..."
            className="w-full bg-white dark:bg-[#1C1510] border border-orange-200/90 dark:border-[#382A20] rounded-full pl-4 pr-11 py-2.5 text-[15px] sm:text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20 shadow-xs transition-all font-sans"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            aria-label="Send message"
            className={`absolute right-1.5 w-7 h-7 sm:w-6 sm:h-6 rounded-full flex items-center justify-center transition-all ${
              input.trim() && !isLoading
                ? "bg-orange-600 text-white hover:bg-orange-700 active:scale-95 shadow-xs cursor-pointer"
                : "bg-stone-100 dark:bg-stone-800 text-stone-400 dark:text-stone-600 cursor-not-allowed opacity-60"
            }`}
          >
            <ArrowUp className="w-4 h-4 sm:w-3.5 sm:h-3.5 stroke-[2.5]" />
          </button>
        </form>
      </div>
    </div>
  );
};
