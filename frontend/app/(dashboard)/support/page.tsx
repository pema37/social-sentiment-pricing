'use client';

/**
 * AI Support Page
 * 
 * PATCHED (2025-01-07): Fixed silent failures
 * - Use api client instead of raw fetch (includes auth token)
 * - Check response status before parsing
 * - Show error state to user
 */

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { MessageCircle, Send, Sparkles, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isError?: boolean;
}

interface TopicSuggestion {
  id: string;
  label: string;
  description: string;
}

interface ChatResponse {
  message: string;
  topic_detected?: string;
  suggested_actions?: string[];
  timestamp: string;
}

interface TopicsResponse {
  topics: TopicSuggestion[];
  default_greeting: string;
  suggested_questions: string[];
}

export default function SupportPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  // Fetch topic suggestions
  const { data: topicsData, isLoading: topicsLoading, error: topicsError } = useQuery({
    queryKey: ['support-topics'],
    queryFn: async () => {
      return api.get<TopicsResponse>('/api/v1/support/topics');
    },
    retry: 2,
  });

  // Chat mutation with proper error handling
  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      return api.post<ChatResponse>('/api/v1/support/chat', {
        message,
        conversation_history: messages
          .filter(m => !m.isError)  // Don't send error messages to AI
          .slice(-10)
          .map(m => ({ role: m.role, content: m.content })),
        topic: selectedTopic
      });
    },
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.message,
        timestamp: data.timestamp || new Date().toISOString()
      }]);
    },
    onError: (error: Error) => {
      // Show error message in chat
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I'm having trouble responding right now. ${error.message || 'Please try again.'}`,
        timestamp: new Date().toISOString(),
        isError: true
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

  const handleRetry = () => {
    // Remove the last error message and retry
    const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');
    if (lastUserMessage) {
      setMessages(prev => prev.filter(m => !m.isError));
      chatMutation.mutate(lastUserMessage.content);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-[#E5E7EB]">
        <div className="p-2 bg-linear-to-br from-purple-500 to-blue-500 rounded-lg">
          <Sparkles className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-[#111827]">AI Support Assistant</h1>
          <p className="text-sm text-[#6B7280]">Get instant help with ActualPrice</p>
        </div>
        <span className="ml-auto px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full font-medium">
          AI Powered
        </span>
      </div>

      {/* Topics Error State */}
      {topicsError && (
        <div className="p-4 bg-red-50 border-b border-red-200">
          <div className="flex items-center gap-2 text-red-600 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>Unable to load topics. The AI assistant is still available.</span>
          </div>
        </div>
      )}

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
              {topicsLoading 
                ? "Loading..." 
                : topicsData?.default_greeting || "Hi! How can I help you today?"}
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
                  : msg.isError
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : 'bg-white text-[#111827] border border-[#E5E7EB]'
              }`}
            >
              {msg.role === 'assistant' && !msg.isError && (
                <div className="flex items-center gap-1 mb-1 text-xs text-purple-600">
                  <Sparkles className="w-3 h-3" />
                  AI Response
                </div>
              )}
              {msg.isError && (
                <div className="flex items-center gap-1 mb-1 text-xs text-red-600">
                  <AlertCircle className="w-3 h-3" />
                  Error
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.isError && (
                <button
                  onClick={handleRetry}
                  className="mt-2 flex items-center gap-1 text-xs text-red-600 hover:text-red-800"
                >
                  <RefreshCw className="w-3 h-3" />
                  Try again
                </button>
              )}
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


