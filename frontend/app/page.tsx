"use client";

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Mic,
  MicOff,
  Send,
  Image,
  Loader2,
  Leaf,
  MessageSquare,
  Camera,
  Upload,
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  inputType?: 'voice' | 'text' | 'image';
  timestamp: Date;
  metadata?: any;
  agentResults?: any[];
}

interface ProcessingStatus {
  isConnected: boolean;
  currentStatus: string;
  agentsRun: string[];
  successCount: number;
  errorCount: number;
}

export default function KrishiMitra() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [textInput, setTextInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [activeInput, setActiveInput] = useState<'text' | 'voice' | 'image'>('text');
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>({
    isConnected: false,
    currentStatus: '',
    agentsRun: [],
    successCount: 0,
    errorCount: 0
  });

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentAssistantMessageRef = useRef<string>('');
  const finalResponseReceivedRef = useRef<boolean>(false);
  const processingCompleteRef = useRef<boolean>(false);

  // Initialize voice recording
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        sendVoiceMessage(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setActiveInput('voice');
    } catch (error) {
      console.error('Error accessing microphone:', error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Handle image selection
  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
      setActiveInput('image');
    }
  };

  const removeImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Send messages to backend
  const sendTextMessage = () => {
    if (!textInput.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: textInput,
      inputType: 'text',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    connectToBackend(textInput);
    setTextInput('');
  };

  const sendVoiceMessage = (audioBlob: Blob) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: 'Voice message sent',
      inputType: 'voice',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    // For now, convert to text placeholder - you'll need to implement audio processing
    connectToBackend('Voice input received - processing...');
  };

  const sendImageMessage = () => {
    if (!selectedImage) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: `Image uploaded: ${selectedImage.name}`,
      inputType: 'image',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    // For now, convert to text placeholder - you'll need to implement image processing
    connectToBackend(`Image analysis requested for: ${selectedImage.name}`);
    removeImage();
  };

  // SSE connection to your Django backend
  const connectToBackend = (query: string) => {
    setIsLoading(true);
    setProcessingStatus(prev => ({ ...prev, isConnected: true, currentStatus: 'Connecting...' }));

    // Reset current assistant message
    currentAssistantMessageRef.current = '';

    // Create assistant message placeholder
    const assistantMessageId = (Date.now() + 1).toString();
    let assistantMessage: Message = {
      id: assistantMessageId,
      type: 'assistant',
      content: '',
      timestamp: new Date(),
      agentResults: []
    };

    setMessages(prev => [...prev, assistantMessage]);

    // Reset the final response flag
    finalResponseReceivedRef.current = false;

    // Send POST request to your SSE endpoint
    fetch('http://localhost:8000/api/test/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: query }),
    })
      .then(response => {
        if (response.ok) {
          // The response itself is the SSE stream
          const reader = response.body?.getReader();
          const decoder = new TextDecoder();

          const readStream = async () => {
            try {
              while (true) {
                const { done, value } = await reader!.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                  if (line.startsWith('event: ')) {
                    const eventType = line.substring(7).trim();
                    continue;
                  }

                  if (line.startsWith('data: ')) {
                    const data = line.substring(6).trim();
                    if (!data) continue;

                    try {
                      // Try to parse as JSON first
                      const jsonData = JSON.parse(data);
                      handleSSEEvent(jsonData, assistantMessageId);
                    } catch {
                      // If not JSON, treat as plain text
                      handleSSEEvent(data, assistantMessageId);
                    }
                  }
                }
              }
            } catch (error) {
              console.error('Stream reading error:', error);
              handleConnectionError();
            } finally {
              setIsLoading(false);
              setProcessingStatus(prev => ({ ...prev, isConnected: false }));
            }
          };

          readStream();
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      })
      .catch(error => {
        console.error('Connection error:', error);
        handleConnectionError();
      });
  };

  const handleSSEEvent = (data: any, assistantMessageId: string) => {
    // If final response has been received, don't update the message content anymore
    if (finalResponseReceivedRef.current) {
      return;
    }

    if (typeof data === 'string') {
      // Handle plain text responses
      if (data.includes('Query processing completed successfully')) {
        finalResponseReceivedRef.current = true;
        return;
      }

      if (data.includes('Processing completed successfully!')) {
        processingCompleteRef.current = true;
        return;
      }

      if (processingCompleteRef.current) {
        // After processing complete, accumulate the response
        currentAssistantMessageRef.current =
          (currentAssistantMessageRef.current ? currentAssistantMessageRef.current + '\n' : '') + data;
        updateAssistantMessage(assistantMessageId, currentAssistantMessageRef.current);
      } else {
        // Before processing complete, show in-place updates
        updateAssistantMessage(assistantMessageId, data);
      }
      return;
    }

    // Handle different event types based on your backend
    if (data.event) {
      switch (data.event) {
        case 'connected':
          setProcessingStatus(prev => ({
            ...prev,
            currentStatus: 'Connected to Farm AI Assistant'
          }));
          updateAssistantMessage(assistantMessageId, 'Connecting to Farm AI Assistant...');
          break;

        case 'status':
          const statusMsg = typeof data === 'string' ? data : data.message || 'Processing...';
          setProcessingStatus(prev => ({
            ...prev,
            currentStatus: statusMsg
          }));
          updateAssistantMessage(assistantMessageId, statusMsg);
          break;

        case 'meta':
          // Handle metadata about the processing
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, metadata: data }
                : msg
            )
          );

          setProcessingStatus(prev => ({
            ...prev,
            agentsRun: data.agents_run || [],
            successCount: data.success_count || 0,
            errorCount: data.error_count || 0
          }));
          break;

        case 'agent_result':
          // Update the message with the latest agent result
          const agentMsg = `Processing with ${data.agent}: ${data.response}`;
          updateAssistantMessage(assistantMessageId, agentMsg);
          // Still store the results for reference
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? {
                  ...msg,
                  agentResults: [...(msg.agentResults || []), data]
                }
                : msg
            )
          );
          break;

        case 'final_response':
          // Set the flag to prevent further updates
          finalResponseReceivedRef.current = true;
          console.log(currentAssistantMessageRef.current)
          // Store and display the final response
          currentAssistantMessageRef.current = typeof data === 'string' ? data : data.response || '';
          updateAssistantMessage(assistantMessageId, currentAssistantMessageRef.current);
          break;

        case 'complete':
          setIsLoading(false);
          setProcessingStatus(prev => ({
            ...prev,
            isConnected: false,
            currentStatus: 'Processing completed'
          }));
          // Now we can set the final response flag as all content has been received
          finalResponseReceivedRef.current = true;
          break;

        case 'error':
        case 'processing_error':
          const errorMessage = typeof data === 'string' ? data : data.message || 'An error occurred';
          currentAssistantMessageRef.current = `Error: ${errorMessage}`;
          updateAssistantMessage(assistantMessageId, currentAssistantMessageRef.current);
          handleConnectionError();
          break;

        case 'timeout':
          currentAssistantMessageRef.current = 'Request timed out. Please try again.';
          updateAssistantMessage(assistantMessageId, currentAssistantMessageRef.current);
          handleConnectionError();
          break;
      }
    } else {
      // Handle direct data without event wrapper
      if (data.agent && data.response) {
        // Agent result
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessageId
              ? {
                ...msg,
                agentResults: [...(msg.agentResults || []), data]
              }
              : msg
          )
        );
      } else if (typeof data === 'object' && data.intent_classification) {
        // Metadata
        setMessages(prev =>
          prev.map(msg =>
            msg.id === assistantMessageId
              ? { ...msg, metadata: data }
              : msg
          )
        );
      }
    }
  };

  const updateAssistantMessage = (messageId: string, content: string) => {
    // Process the content to ensure proper markdown formatting
    let formattedContent = content;

    // Ensure lists have a newline before them
    formattedContent = formattedContent.replace(/([^\n])\n\*/g, '$1\n\n*');
    // Ensure headers have a newline before them
    formattedContent = formattedContent.replace(/([^\n])\n#/g, '$1\n\n#');

    setMessages(prev =>
      prev.map(msg =>
        msg.id === messageId
          ? { ...msg, content: formattedContent }
          : msg
      )
    );
    // Reset the current assistant message reference since we're not accumulating anymore
    currentAssistantMessageRef.current = formattedContent;
  };

  const handleConnectionError = () => {
    setIsLoading(false);
    setProcessingStatus(prev => ({
      ...prev,
      isConnected: false,
      currentStatus: 'Connection error'
    }));
  };

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-green-100">
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-full">
              <Leaf className="h-8 w-8 text-green-600" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">कृषिमित्र</h1>
              <p className="text-sm text-gray-600">AI Agricultural Assistant</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Messages */}
        <Card className="min-h-[400px] max-h-[500px] overflow-y-auto">
          <CardContent className="p-6 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-12">
                <Leaf className="h-16 w-16 text-green-300 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-gray-700 mb-2">
                  Welcome to कृषिमित्र
                </h3>
                <p className="text-gray-500 max-w-md mx-auto">
                  Your intelligent agricultural assistant. Ask questions about crops, pests,
                  weather, or market prices using voice, text, or images.
                </p>
              </div>
            )}

            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "flex gap-3 max-w-[85%]",
                  message.type === 'user' ? "ml-auto flex-row-reverse" : ""
                )}
              >
                <div className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                  message.type === 'user' ? "bg-green-100" : "bg-emerald-100"
                )}>
                  {message.type === 'user' ? (
                    <div className="w-4 h-4 bg-green-600 rounded-full" />
                  ) : (
                    <Leaf className="w-4 h-4 text-emerald-600" />
                  )}
                </div>

                <div className={cn(
                  "px-4 py-3 rounded-2xl",
                  message.type === 'user'
                    ? "bg-green-600 text-white ml-auto"
                    : "bg-gray-100 text-gray-800"
                )}>
                  {message.inputType && message.type === 'user' && (
                    <Badge variant="secondary" className="mb-2 text-xs">
                      {message.inputType === 'voice' && <Mic className="w-3 h-3 mr-1" />}
                      {message.inputType === 'image' && <Camera className="w-3 h-3 mr-1" />}
                      {message.inputType === 'text' && <MessageSquare className="w-3 h-3 mr-1" />}
                      {message.inputType}
                    </Badge>
                  )}
                  {message.type === 'assistant' ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                    // className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 prose-headings:my-2"
                    >
                      {message.content}
                    </ReactMarkdown>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-3 max-w-[85%]">
                <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center">
                  <Leaf className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="px-4 py-3 rounded-2xl bg-gray-100">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm text-gray-600">
                      {processingStatus.currentStatus || 'Processing your request...'}
                    </span>
                  </div>
                  {processingStatus.agentsRun.length > 0 && (
                    <div className="mt-2 text-xs text-gray-500">
                      <div>Agents: {processingStatus.agentsRun.join(', ')}</div>
                      <div>Success: {processingStatus.successCount} | Errors: {processingStatus.errorCount}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Input Section */}
        <Card>
          <CardContent className="p-6">
            {/* Input Type Selector */}
            <div className="flex gap-2 mb-6">
              <Button
                variant={activeInput === 'text' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInput('text')}
                className="flex items-center gap-2"
              >
                <MessageSquare className="w-4 h-4" />
                Text
              </Button>
              <Button
                variant={activeInput === 'voice' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInput('voice')}
                className="flex items-center gap-2"
              >
                <Mic className="w-4 h-4" />
                Voice
              </Button>
              <Button
                variant={activeInput === 'image' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveInput('image')}
                className="flex items-center gap-2"
              >
                <Camera className="w-4 h-4" />
                Image
              </Button>
            </div>

            {/* Text Input */}
            {activeInput === 'text' && (
              <div className="space-y-4">
                <Textarea
                  placeholder="Ask about crops, pests, weather, or market prices..."
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  className="min-h-[100px] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendTextMessage();
                    }
                  }}
                />
                <Button
                  onClick={sendTextMessage}
                  disabled={!textInput.trim() || isLoading}
                  className="w-full sm:w-auto"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Send Message
                </Button>
              </div>
            )}

            {/* Voice Input */}
            {activeInput === 'voice' && (
              <div className="text-center space-y-6">
                <div className="flex items-center justify-center">
                  <div className={cn(
                    "w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300",
                    isRecording
                      ? "bg-red-100 animate-pulse"
                      : "bg-green-100 hover:bg-green-200"
                  )}>
                    <Button
                      size="lg"
                      onClick={isRecording ? stopRecording : startRecording}
                      disabled={isLoading}
                      className={cn(
                        "w-16 h-16 rounded-full",
                        isRecording
                          ? "bg-red-600 hover:bg-red-700"
                          : "bg-green-600 hover:bg-green-700"
                      )}
                    >
                      {isRecording ? (
                        <MicOff className="w-8 h-8" />
                      ) : (
                        <Mic className="w-8 h-8" />
                      )}
                    </Button>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-gray-600 mb-2">
                    {isRecording ? 'Recording... Tap to stop' : 'Tap to start recording'}
                  </p>
                  {isRecording && (
                    <div className="flex justify-center">
                      <div className="flex gap-1">
                        {[...Array(5)].map((_, i) => (
                          <div
                            key={i}
                            className="w-1 bg-red-500 animate-pulse"
                            style={{
                              height: Math.random() * 20 + 10,
                              animationDelay: `${i * 0.1}s`
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Image Input */}
            {activeInput === 'image' && (
              <div className="space-y-4">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageSelect}
                  className="hidden"
                />

                {!imagePreview ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-green-300 rounded-lg p-8 text-center cursor-pointer hover:border-green-400 transition-colors"
                  >
                    <Upload className="w-12 h-12 text-green-400 mx-auto mb-4" />
                    <p className="text-green-700 font-medium">Click to upload crop image</p>
                    <p className="text-sm text-gray-500 mt-2">
                      Upload images of crops, pests, or diseases for analysis
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="relative inline-block">
                      <img
                        src={imagePreview}
                        alt="Selected crop"
                        className="w-full max-w-sm h-48 object-cover rounded-lg"
                      />
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={removeImage}
                        className="absolute top-2 right-2"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                    <Button
                      onClick={sendImageMessage}
                      disabled={!selectedImage || isLoading}
                      className="w-full sm:w-auto"
                    >
                      <Image className="w-4 h-4 mr-2" />
                      Analyze Image
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Connection Status */}
            {processingStatus.isConnected && (
              <div className="mt-4 flex items-center justify-center gap-2 text-sm text-green-600">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                {processingStatus.currentStatus || 'Connected to KrishiMitra AI'}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Features Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: '🌱', title: 'Crop Diseases', desc: 'Identify and treat plant diseases' },
            { icon: '🐛', title: 'Pest Control', desc: 'Combat harmful insects and pests' },
            { icon: '🌤️', title: 'Weather Insights', desc: 'Get weather forecasts and alerts' },
            { icon: '💰', title: 'Market Prices', desc: 'Track commodity prices and trends' }
          ].map((feature, index) => (
            <Card key={index} className="text-center p-4">
              <div className="text-3xl mb-2">{feature.icon}</div>
              <h3 className="font-semibold text-gray-800 mb-1">{feature.title}</h3>
              <p className="text-sm text-gray-600">{feature.desc}</p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}