import { ResizablePanelGroup, ResizablePanel } from "@/components/ui/resizable";
import WorkflowPanel from "@/components/WorkflowPanel";
import ChatPanel from "@/components/ChatPanel";
import { useState, useEffect } from "react";
import { useWebSocket } from "@/lib/websocket";
import { useToast } from "@/hooks/use-toast";

export default function Home() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const { toast } = useToast();
  const { ws, isConnected } = useWebSocket();

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received WebSocket message:', data);

        // ping-pongメッセージの処理
        if (data.type === 'pong') {
          console.log("Received pong response at:", data.timestamp);
          return;
        }

        if (data.type === 'task_executed') {
          updateTask(data.task);
        } else if (data.type === 'task_created') {
          handleNewTask(data.task);
        } else if (data.type === 'tasks_deleted') {
          // タスクが削除された時の処理
          setTasks([]);
          toast({
            title: "タスク削除",
            description: "すべてのタスクが削除されました",
          });
        }

        // エラーメッセージの処理
        if (data.type === 'error') {
          toast({
            title: "エラー",
            description: data.message,
            variant: "destructive",
          });
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };

    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [ws, toast]);

  // 残りのコードは変更なし
  const handleNewTask = (task: Task) => {
    console.log('Creating new task:', task);
    setTasks(prev => [...prev, task]);
  };

  const updateTask = (updatedTask: Task) => {
    console.log('Updating task:', updatedTask);
    setTasks(prev => prev.map(task =>
      task.id === updatedTask.id ? updatedTask : task
    ));

    if (updatedTask.status === 'completed') {
      toast({
        title: "タスク完了",
        description: `${updatedTask.name}が完了しました`,
      });
    } else if (updatedTask.status === 'failed') {
      toast({
        title: "タスク失敗",
        description: `${updatedTask.name}が失敗しました`,
        variant: "destructive",
      });
    }
  };

  return (
    <>
      <div className="h-screen">
        <ResizablePanelGroup direction="horizontal">
          <ResizablePanel defaultSize={100}>
            <WorkflowPanel tasks={tasks} ws={ws} />
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
      <ChatPanel onNewTask={handleNewTask} ws={ws} />
    </>
  );
}

export interface Task {
  id: string;
  name: string;
  type: string;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  dependencies: string[];
}