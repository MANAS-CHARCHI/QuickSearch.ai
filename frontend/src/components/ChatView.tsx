import React, { useState, useRef, useEffect } from "react";
import { Sparkles } from "lucide-react";
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
    <div className="w-full max-w-2xl mx-auto flex flex-col h-full sm:h-[calc(100vh-160px)] sm:max-h-[580px] sm:min-h-[420px] bg-white dark:bg-[#1C1510] border-0 sm:border border-orange-200/80 dark:border-[#2D2118] rounded-none sm:rounded-xl shadow-none sm:shadow-val overflow-hidden transition-all">
      {/* Clean Assistant Header (Desktop Only to prevent double header on mobile) */}
      <div className="hidden sm:flex shrink-0 px-4 py-2.5 border-b border-orange-200/60 dark:border-[#2D2118] items-center justify-between bg-orange-50/60 dark:bg-[#221913] font-sans">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-stone-900 dark:text-white">
            Vault Assistant
          </span>
          <span className="text-[10px] text-stone-400">•</span>
          <span className="text-xs text-stone-500 dark:text-stone-400">
            Ask questions about your uploaded documents & FAQs
          </span>
        </div>

        <div className="text-[11px] text-stone-400 font-sans">
          Encrypted • Private
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-4 space-y-3 font-sans min-h-0">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start space-x-2 ${
              msg.sender === "user" ? "justify-end" : "justify-start"
            }`}
          >
            {msg.sender === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20 flex items-center justify-center font-semibold text-[10px] flex-shrink-0 mt-0.5">
                VA
              </div>
            )}

            <div
              className={`max-w-[88%] sm:max-w-[82%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed transition-all ${
                msg.sender === "user"
                  ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-950 rounded-br-sm shadow-sm font-medium"
                  : "bg-stone-50 dark:bg-[#181820] text-stone-800 dark:text-stone-200 border border-stone-200 dark:border-stone-800 rounded-bl-sm"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>

              {/* Source references */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2.5 pt-1.5 border-t border-stone-200/80 dark:border-stone-800 flex items-center flex-wrap gap-1 font-mono">
                  <span className="text-[9px] text-stone-400">ref:</span>
                  {msg.sources.map((src, idx) => (
                    <span
                      key={idx}
                      className="text-[9px] bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 px-1.5 py-0.5 rounded border border-indigo-500/20 hover:border-indigo-400 cursor-pointer transition-colors font-medium"
                    >
                      @vault.city/{src}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {msg.sender === "user" && (
              <div className="w-6 h-6 rounded-full bg-stone-200 dark:bg-stone-800 text-stone-700 dark:text-stone-300 flex items-center justify-center font-medium flex-shrink-0 mt-0.5 text-[10px]">
                You
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center space-x-2 text-xs text-stone-500 dark:text-stone-400 bg-stone-50 dark:bg-[#181820] px-3 py-1.5 rounded-lg border border-stone-200 dark:border-stone-800 w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-stone-400 animate-pulse" />
            <span className="text-[11px] font-sans">
              Searching your documents...
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Questions */}
      {messages.length <= 2 && (
        <div className="shrink-0 px-3 py-1.5 flex items-center gap-1.5 overflow-x-auto border-t border-orange-200/60 dark:border-[#2D2118] bg-orange-50/40 dark:bg-[#221913]/60 font-sans">
          <Sparkles className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
          {quickPrompts.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => onSendMessage(prompt)}
              className="text-xs whitespace-nowrap bg-white dark:bg-[#1C1510] hover:bg-orange-50/60 dark:hover:bg-[#281D16] border border-orange-200/70 dark:border-[#2D2118] text-stone-700 dark:text-stone-300 px-2.5 py-1 rounded-lg transition-all cursor-pointer font-sans"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Chat Input Field (with safe area and dock offset on mobile) */}
      <form
        onSubmit={handleSubmit}
        className="shrink-0 p-2.5 sm:p-2.5 pb-[calc(74px+env(safe-area-inset-bottom,0px))] sm:pb-2.5 border-t border-orange-200/60 dark:border-[#2D2118] bg-white dark:bg-[#1C1510] font-sans"
      >
        <div className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about your documents..."
            className="w-full bg-orange-50/30 dark:bg-[#251A12] border border-orange-200/70 dark:border-[#382A20] rounded-lg pl-3 pr-16 py-2 text-[16px] sm:text-xs text-stone-900 dark:text-white placeholder-stone-400 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/20 transition-all font-sans"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-1 px-3 py-1 bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-400 dark:text-stone-950 disabled:opacity-20 rounded-md text-xs font-sans font-semibold transition-all hover:opacity-90 cursor-pointer flex items-center space-x-1"
          >
            <span>Ask</span>
          </button>
        </div>
      </form>
    </div>
  );
};
