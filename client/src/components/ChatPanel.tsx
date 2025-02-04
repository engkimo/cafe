import { useState, useRef, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Send } from "lucide-react";
import type { Task } from "@/pages/Home";
import type { TaskSuggestion } from "@/lib/taskSuggestion";
import { convertSuggestionToTask } from "@/lib/taskSuggestion";
import { useToast } from "@/hooks/use-toast";
import { motion, AnimatePresence } from "framer-motion";
import { Rnd } from "react-rnd";

interface ChatPanelProps {
  onNewTask: (task: Task) => void;
  ws: WebSocket | null;
}

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'system';
  suggestedTasks?: TaskSuggestion[];
}

export default function ChatPanel({ onNewTask, ws }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoSaveMode, setAutoSaveMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const handleAutoSaveChange = (checked: boolean) => {
    setAutoSaveMode(checked);
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'set_auto_save',
        enabled: checked
      }));
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received WebSocket message:', data);

        if (data.type === 'message') {
          const newMessage: Message = {
            id: Date.now().toString(),
            content: data.content,
            sender: 'system',
            suggestedTasks: data.suggested_tasks || []
          };

          setMessages(prev => [...prev, newMessage]);
          setLoading(false);
          console.log('Added new message:', newMessage);

          if (data.suggested_tasks?.length > 0) {
            for (const suggestion of data.suggested_tasks) {
              console.log('Creating task from suggestion:', suggestion);
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                  type: 'create_task',
                  task: convertSuggestionToTask(suggestion)
                }));
              }
            }
          }
        } else if (data.type === 'error') {
          setLoading(false);
          toast({
            title: "エラー",
            description: data.message,
            variant: "destructive",
          });
        }
      } catch (error) {
        setLoading(false);
        console.error('Failed to process WebSocket message:', error);
        toast({
          title: "エラー",
          description: "メッセージの処理中にエラーが発生しました",
          variant: "destructive",
        });
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [ws, toast]);

  useEffect(() => {
    const scroll = () => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };
    scroll();
  }, []);

  const handleSend = async () => {
    if (!input.trim() || !ws || ws.readyState !== WebSocket.OPEN) {
      toast({
        title: "エラー",
        description: "メッセージを送信できません",
        variant: "destructive",
      });
      return;
    }

    const newMessage: Message = {
      id: Date.now().toString(),
      content: input,
      sender: 'user'
    };

    setMessages(prev => [...prev, newMessage]);
    setInput('');
    setLoading(true);

    try {
      ws.send(JSON.stringify({
        type: 'message',
        content: input
      }));
    } catch (error) {
      console.error('Failed to send message:', error);
      setLoading(false);
      toast({
        title: "エラー",
        description: "メッセージの送信に失敗しました",
        variant: "destructive",
      });
    }
  };

  const ThinkingIndicator = () => (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-lg p-3 bg-lightcyan flex items-center gap-1 text-sm text-foreground font-bold">
        <span>thinking</span>
        <AnimatePresence>
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 0] }}
              transition={{
                duration: 1,
                repeat: Number.POSITIVE_INFINITY,
                delay: i * 0.2,
                ease: "easeInOut"
              }}
            >
              .
            </motion.span>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );

  return (
    <Rnd
      default={{
        x: window.innerWidth - 420,
        y: 20,
        width: 400,
        height: 600
      }}
      minWidth={300}
      minHeight={400}
      bounds="window"
      dragHandleClassName="drag-handle"
    >
      <Card className="h-full flex flex-col shadow-lg border-2">
        <div className="p-4 border-b cursor-move drag-handle">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">チャット</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">自動保存</span>
              <Switch
                checked={autoSaveMode}
                onCheckedChange={handleAutoSaveChange}
                aria-label="自動保存モード"
              />
            </div>
          </div>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-4">
            {messages.map((msg) => (
              <div key={msg.id}>
                <div
                  className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      msg.sender === 'user'
                        ? 'bg-beige text-foreground'
                        : 'bg-lightcyan text-foreground'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
                {msg.suggestedTasks && msg.suggestedTasks.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {msg.suggestedTasks.map((task) => (
                      <div key={`${task.name}-${task.confidence}`} className="text-sm text-muted-foreground">
                        提案されたタスク: {task.name} ({Math.round(task.confidence * 100)}% 信頼度)
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <AnimatePresence>
              {loading && <ThinkingIndicator />}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
        <div className="p-4 border-t">
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="メッセージを入力..."
              onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              disabled={loading || !ws || ws.readyState !== WebSocket.OPEN}
            />
            <motion.div whileTap={{ scale: 0.95 }}>
              <Button
                onClick={handleSend}
                disabled={loading || !ws || ws.readyState !== WebSocket.OPEN}
                className="bg-beige hover:bg-beige/90 text-foreground"
              >
                <Send className="h-4 w-4" />
              </Button>
            </motion.div>
          </div>
        </div>
      </Card>
    </Rnd>
  );
}