'use client';

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { MessageCircle, Send, Sparkles, Loader2 } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface TopicSuggestion {
  id: string;
  label: string;
  description: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function SupportPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  // Fetch topic suggestions
  const { data: topicsData } = useQuery({
    queryKey: ['support-topics'],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/support/topics`);
      return res.json();
    }
  });

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await fetch(`${API_URL}/api/v1/support/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          conversation_history: messages.slice(-10),
          topic: selectedTopic
        })
      });
      return res.json();
    },
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message,
        timestamp: data.timestamp
      }]);
    }
  });

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return;
    
    // Add user message
    setMessages(prev => [...prev, {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }]);
    
    chatMutation.mutate(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-[#E5E7EB]">
        <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
          <Sparkles className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-[#111827]">AI Support Assistant</h1>
          <p className="text-sm text-[#6B7280]">Powered by GPT-4o-mini</p>
        </div>
        <span className="ml-auto px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full font-medium">
          AI Powered
        </span>
      </div>

      {/* Topic Pills */}
      {messages.length === 0 && topicsData?.topics && (
        <div className="p-4 border-b border-[#E5E7EB]">
          <p className="text-sm text-[#6B7280] mb-3">Select a topic:</p>
          <div className="flex flex-wrap gap-2">
            {topicsData.topics.map((topic: TopicSuggestion) => (
              <button
                key={topic.id}
                onClick={() => setSelectedTopic(topic.id)}
                className={`px-3 py-2 rounded-full text-sm transition-all ${
                  selectedTopic === topic.id
                    ? 'bg-[#1F2937] text-white'
                    : 'bg-[#F3F4F6] hover:bg-[#E5E7EB] text-[#374151]'
                }`}
              >
                {topic.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F8F9FB]">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <MessageCircle className="w-12 h-12 mx-auto text-[#D1D5DB] mb-4" />
            <p className="text-[#6B7280]">
              {topicsData?.default_greeting || "Hi! How can I help you today?"}
            </p>
            {topicsData?.suggested_questions && (
              <div className="mt-6 space-y-2">
                {topicsData.suggested_questions.slice(0, 3).map((q: string, i: number) => (
                  <button
                    key={i}
                    onClick={() => setInput(q)}
                    className="block mx-auto px-4 py-2 text-sm text-[#1F2937] hover:bg-white rounded-lg border border-[#E5E7EB]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-[#1F2937] text-white'
                  : 'bg-white text-[#111827] border border-[#E5E7EB]'
              }`}
            >
              {msg.role === 'assistant' && (
                <div className="flex items-center gap-1 mb-1 text-xs text-purple-600">
                  <Sparkles className="w-3 h-3" />
                  AI Response
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}
        
        {chatMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-white p-3 rounded-lg border border-[#E5E7EB]">
              <Loader2 className="w-5 h-5 animate-spin text-[#6B7280]" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-[#E5E7EB] bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask anything about ActualPrice..."
            className="flex-1 px-4 py-2 border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1F2937] text-[#111827]"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || chatMutation.isPending}
            className="px-4 py-2 bg-[#1F2937] text-white rounded-lg hover:bg-[#374151] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
