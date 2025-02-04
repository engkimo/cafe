import { memo, useState } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import type { Task } from "@/pages/Home";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, Pause, RotateCcw, Save, Brain, AlertCircle } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface TaskInputs {
  attendees?: string;
  subject?: string;
  body?: string;
  to?: string;
  start_time?: string;
  end_time?: string;
  [key: string]: string | undefined;
}

export interface TaskNodeData extends Record<string, unknown> {
  task: Task;
  onExecute?: (taskId: string) => void;
  onUpdate?: (taskId: string, inputs: TaskInputs) => void;
  isExecuting?: boolean;
  autoSaveMode?: boolean;
  [key: string]: unknown;
}

interface TaskNodeProps extends NodeProps {
  data: {
    data: TaskNodeData;
  };
}

function TaskNode({ data }: TaskNodeProps) {
  const { task, onExecute, isExecuting, autoSaveMode } = data.data;
  const [showError, setShowError] = useState(false);

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-500',
    running: 'bg-blue-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500'
  };

  const statusLabels: Record<string, string> = {
    pending: '待機中',
    running: '実行中',
    completed: '完了',
    failed: '失敗'
  };

  const handleExecute = () => {
    if (onExecute && task.status === 'pending') {
      onExecute(task.id);
    }
  };

  const renderButton = () => {
    if (task.status === 'completed' || task.status === 'failed') {
      return (
        <Button
          size="sm"
          variant="outline"
          onClick={() => {}}
          className="px-2 h-8"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      );
    }

    if (task.status === 'pending' && isExecuting) {
      return (
        <Button
          size="sm"
          variant="outline"
          onClick={handleExecute}
          className="px-2 h-8"
        >
          <Pause className="h-4 w-4" />
        </Button>
      );
    }

    if (task.status === 'pending') {
      return (
        <Button
          size="sm"
          variant="outline"
          onClick={handleExecute}
          className="px-2 h-8"
        >
          <Play className="h-4 w-4" />
        </Button>
      );
    }

    return null;
  };

  const getDefaultTimes = () => {
    const now = new Date();
    const startTime = new Date(now.getTime() + 30 * 60000);
    const endTime = new Date(now.getTime() + 60 * 60000);
    
    const formatDateTime = (date: Date) => {
      date.setSeconds(0);
      return date.toISOString().slice(0, 19);
    };

    const times = {
      start_time: formatDateTime(startTime),
      end_time: formatDateTime(endTime)
    };
    
    return times;
  };

  const defaultInputs = {
    'Create Google Calendar Event': {
      attendees: '',
      ...getDefaultTimes(),
      subject: ''
    },
    'Send Gmail': {
      to: '',
      subject: '',
      body: ''
    }
  };

  const [inputs, setInputs] = useState(() => {
    const defaults = defaultInputs[task.type as keyof typeof defaultInputs] || {};
    return {
      ...defaults,
      ...Object.fromEntries(
        Object.entries(task.inputs).filter(([_, value]) => value !== '')
      )
    };
  });

  const handleInputChange = (key: string, value: string) => {
    let processedValue = value;

    if (key.includes('time')) {
      if (value === '') {
        const { start_time, end_time } = getDefaultTimes();
        processedValue = key === 'start_time' ? start_time : end_time;
      } else {
        try {
          const date = new Date(value);
          const timestamp = date.getTime();
          if (!Number.isNaN(timestamp)) {
            date.setSeconds(0);
            processedValue = date.toISOString().slice(0, 19);
          } else {
            processedValue = value;
          }
        } catch (e) {
          console.error('Invalid date format:', e);
          processedValue = value;
        }
      }
    }

    if (key === 'attendees' || key === 'to') {
      processedValue = value.trim();
    }

    setInputs(prev => ({
      ...prev,
      [key]: processedValue
    }));

    // 自動保存モードの場合、入力時に自動保存
    if (autoSaveMode && data.data.onUpdate) {
      const updatedInputs = {
        ...inputs,
        [key]: processedValue
      };
      data.data.onUpdate(task.id, updatedInputs);
    }
  };

  const handleSave = () => {
    if (data.data.onUpdate) {
      console.log('Saving task inputs:', inputs);
      
      const processedInputs = { ...inputs } as TaskInputs;
      
      const timeFields = ['start_time', 'end_time'] as const;
      for (const field of timeFields) {
        const value = processedInputs[field];
        if (value) {
          const date = new Date(value);
          if (!Number.isNaN(date.getTime())) {
            date.setSeconds(0);
            const formattedDate = date.toISOString().slice(0, 19);
            console.log(`Processing ${field}:`, value, '→', formattedDate);
            processedInputs[field] = formattedDate;
          }
        }
      }
      
      console.log('Final processed inputs:', processedInputs);
      console.log('Task type:', task.type);
      data.data.onUpdate(task.id, processedInputs);
    }
  };

  const renderTaskDetails = () => {
    return (
      <div className="p-4 space-y-4 max-h-[400px]">
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h4 className="font-medium">入力パラメータ</h4>
            {autoSaveMode && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Brain className="h-3 w-3" />
                <span>自動保存</span>
              </div>
            )}
          </div>
          <div className="space-y-4">
            <div className="space-y-2">
              {Object.entries(inputs).map(([key, value]) => {
                const inputId = `task-${task.id}-input-${key}`;
                const inputType = key.includes('time') ? 'datetime-local' : 'text';
                const placeholder = {
                  attendees: 'メールアドレスをカンマ区切りで入力',
                  subject: '件名を入力',
                  body: '本文を入力',
                  to: '送信先メールアドレス',
                  start_time: '開始日時',
                  end_time: '終了日時'
                }[key] || '';

                return (
                  <div key={key} className="space-y-1">
                    <label
                      htmlFor={inputId}
                      className="text-xs font-medium"
                    >
                      {key}
                    </label>
                    <input
                      id={inputId}
                      type={inputType}
                      value={value as string}
                      onChange={(e) => handleInputChange(key, e.target.value)}
                      className="w-full px-2 py-1 text-xs border rounded"
                      placeholder={placeholder}
                    />
                  </div>
                );
              })}
            </div>
            {!autoSaveMode && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleSave}
                className="w-full"
              >
                <Save className="h-4 w-4 mr-2" />
                保存
              </Button>
            )}
          </div>
        </div>
        {task.outputs && Object.keys(task.outputs).length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium">出力ログ</h4>
            {task.status === 'failed' && task.outputs.error && (
              <Alert variant="destructive" className="mb-2">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {task.outputs.error}
                </AlertDescription>
              </Alert>
            )}
            <pre className="bg-muted p-2 rounded-md text-xs overflow-x-auto">
              {JSON.stringify(task.outputs, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div>
            <Handle type="target" position={Position.Top} />
            <Card className={`relative w-[280px] ${task.status === 'failed' ? 'border-red-500' : ''}`}>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium">{task.name}</h3>
                    {autoSaveMode && <Brain className="h-4 w-4 text-muted-foreground" />}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className={statusColors[task.status]}>
                      {statusLabels[task.status]}
                    </Badge>
                    {renderButton()}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  <div>タイプ: {task.type}</div>
                  {task.dependencies.length > 0 && (
                    <div>依存関係: {task.dependencies.join(', ')}</div>
                  )}
                </div>
                {task.status === 'running' && (
                  <div className="mt-4">
                    <Progress
                      value={100}
                      className="progress-indeterminate"
                    />
                  </div>
                )}
                {task.status === 'failed' && (
                  <div className="mt-2 flex items-center gap-2 text-red-500 text-sm">
                    <AlertCircle className="h-4 w-4" />
                    <span>エラーが発生しました</span>
                  </div>
                )}
              </CardContent>
            </Card>
            <Handle type="source" position={Position.Bottom} />
          </div>
        </TooltipTrigger>
        <TooltipContent side="right" className="w-[400px] p-0">
          <ScrollArea className="h-[400px]">
            {renderTaskDetails()}
          </ScrollArea>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

const MemoizedTaskNode = memo(TaskNode);
MemoizedTaskNode.displayName = 'TaskNode';

export default MemoizedTaskNode;