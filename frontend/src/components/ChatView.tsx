import React, { useState, useRef, useEffect } from "react";
import { Sparkles, ShieldCheck } from "lucide-react";
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
    "give me my aadhaar number",
    "when does my passport expire?",
    "show my blood sugar level",
    "what was my tax refund?",
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
    <div className="w-full max-w-2xl mx-auto flex flex-col h-full sm:h-[calc(100vh-160px)] sm:max-h-[600px] sm:min-h-[440px] bg-[#FFFCF9] sm:bg-white dark:bg-[#140E0A] sm:dark:bg-[#1C1510] border-0 sm:border border-orange-200/80 dark:border-[#2D2118] rounded-none sm:rounded-2xl shadow-none sm:shadow-val overflow-hidden transition-all relative">
      {/* Desktop Top Bar (vault assistant written at top) */}
      <div className="hidden sm:flex shrink-0 px-4 py-2.5 border-b border-orange-200/60 dark:border-[#2D2118] items-center justify-between bg-orange-50/60 dark:bg-[#221913] font-mono">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded bg-orange-600 flex items-center justify-center text-white text-[9px] font-bold">
            vc
          </div>
          <span className="text-xs font-bold text-stone-900 dark:text-white font-sans">
            vault assistant
          </span>
        </div>

        <div className="flex items-center space-x-1.5 text-[11px] text-stone-400">
          <ShieldCheck className="w-3.5 h-3.5 text-stone-500 dark:text-stone-400" />
          <span>encrypted</span>
        </div>
      </div>

      {/* Messages Scroll Area — Scrollable */}
      <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-4 pb-28 sm:pb-4 space-y-3 font-sans min-h-0">
        {/* If no messages yet */}
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 max-w-sm mx-auto my-auto">
            <div className="w-10 h-10 rounded-xl bg-orange-600 flex items-center justify-center text-white font-bold text-base shadow-sm mb-2 font-mono">
              vc
            </div>
            <h2 className="text-sm font-bold text-stone-900 dark:text-white font-sans">
              vault assistant
            </h2>
            <p className="text-xs text-stone-500 dark:text-stone-400 mt-1">
              ask anything about your encrypted records
            </p>
          </div>
        )}

        {/* Message Feed */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.sender === "user" ? "items-end" : "items-start"
            }`}
          >
            {/* Header tag */}
            <div className={`flex items-center space-x-1.5 mb-1 px-1 ${msg.sender === "user" ? "self-end" : "self-start"}`}>
              {msg.sender === "assistant" ? (
                <>
                  <span className="w-3.5 h-3.5 rounded bg-orange-600 flex items-center justify-center text-white text-[8px] font-bold font-mono">
                    va
                  </span>
                  <span className="text-[10px] font-bold text-stone-800 dark:text-stone-200 font-mono">
                    va
                  </span>
                </>
              ) : (
                <span className="text-[10px] font-mono text-stone-400">
                  you
                </span>
              )}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[90%] sm:max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs sm:text-[13px] leading-relaxed transition-all shadow-xs ${
                msg.sender === "user"
                  ? "bg-stone-900 text-white dark:bg-[#FAF5F0] dark:text-stone-950 rounded-br-xs font-normal"
                  : "bg-white dark:bg-[#1C1510] text-stone-900 dark:text-stone-100 border border-orange-200/80 dark:border-[#2D2118] rounded-tl-xs"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Source references */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 pt-1.5 border-t border-orange-100 dark:border-[#281D15] flex items-center flex-wrap gap-1 font-mono">
                  <span className="text-[9px] text-stone-400">ref:</span>
                  {msg.sources.map((src, idx) => (
                    <span
                      key={idx}
                      className="text-[9px] bg-orange-500/10 text-orange-700 dark:text-orange-400 px-1.5 py-0.5 rounded border border-orange-500/20 font-mono"
                    >
                      @va/{src}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 text-xs text-stone-600 dark:text-stone-400 bg-white dark:bg-[#1C1510] px-3.5 py-2 rounded-xl border border-orange-200/80 dark:border-[#2D2118] w-fit shadow-xs font-mono">
            <span className="flex space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
            <span className="text-[11px]">searching...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Writing Slit — Fixed at Bottom on Mobile */}
      <div className="fixed sm:static bottom-0 left-0 right-0 z-30 bg-[#FFFCF9] sm:bg-white dark:bg-[#140E0A] sm:dark:bg-[#1C1510] border-t border-orange-200/80 dark:border-[#2D2118] p-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom,0px))] sm:p-2.5 shadow-sm">
        {/* Suggestion Chips strip above input slit */}
        {messages.length <= 4 && (
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-2 px-0.5 max-w-2xl mx-auto">
            <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" />
            {quickPrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => onSendMessage(prompt)}
                className="text-[11px] whitespace-nowrap bg-white dark:bg-[#1C1510] hover:bg-orange-50 dark:hover:bg-[#251A12] border border-orange-200/80 dark:border-[#2D2118] text-stone-700 dark:text-stone-300 px-2.5 py-1 rounded-lg transition-all cursor-pointer font-sans shrink-0 shadow-xs active:scale-95"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Input Field Slit with "Ask" / "Ask again" button */}
        <form onSubmit={handleSubmit} className="relative flex items-center max-w-2xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your documents..."
            className="w-full bg-white dark:bg-[#1C1510] border border-orange-200/90 dark:border-[#382A20] rounded-xl pl-3 pr-24 py-2 text-[15px] sm:text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 shadow-xs transition-all font-sans"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-1 px-3 py-1.5 sm:py-1 bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-400 dark:text-stone-950 disabled:opacity-30 rounded-lg text-xs font-mono font-semibold transition-all hover:opacity-90 cursor-pointer flex items-center space-x-1 shrink-0 shadow-xs"
          >
            <span>{isLoading ? "Asking..." : messages.length > 0 ? "Ask again" : "Ask"}</span>
          </button>
        </form>
      </div>
    </div>
  );
};
