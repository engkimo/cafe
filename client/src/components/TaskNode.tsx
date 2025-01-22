import { memo, useState } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import type { Task } from "@/pages/Home";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, Pause, RotateCcw, Save } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";

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
  [key: string]: unknown;
}

interface TaskNodeProps extends NodeProps {
  data: {
    data: TaskNodeData;
  };
}

function TaskNode({ data }: TaskNodeProps) {
  const { task, onExecute, isExecuting } = data.data;

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

  // 現在の日時から30分後と1時間後のデフォルト日時を計算
  const getDefaultTimes = () => {
    const now = new Date();
    const startTime = new Date(now.getTime() + 30 * 60000); // 30分後
    const endTime = new Date(now.getTime() + 60 * 60000);   // 1時間後
    
    // YYYY-MM-DDThh:mm:ss形式に変換（秒を00に設定）
    const formatDateTime = (date: Date) => {
      date.setSeconds(0);
      return date.toISOString().slice(0, 19);
    };

    const times = {
      start_time: formatDateTime(startTime),
      end_time: formatDateTime(endTime)
    };
    
    console.log('Generated default times:', times);
    return times;
  };

  // タスクタイプに応じたデフォルトの入力フィールドを定義
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
    // タスクの既存の入力値がある場合はそれを使用
    return {
      ...defaults,
      ...Object.fromEntries(
        Object.entries(task.inputs).filter(([_, value]) => value !== '')
      )
    };
  });

  const handleInputChange = (key: string, value: string) => {
    let processedValue = value;

    // 日時入力の処理（より柔軟に）
    if (key.includes('time')) {
      if (value === '') {
        // 値が空の場合、デフォルトの日時を設定
        const { start_time, end_time } = getDefaultTimes();
        processedValue = key === 'start_time' ? start_time : end_time;
      } else {
        try {
          // 入力された日時をYYYY-MM-DDThh:mm:ss形式に変換
          const date = new Date(value);
          const timestamp = date.getTime();
          if (!Number.isNaN(timestamp)) {
            // 秒を00に設定
            date.setSeconds(0);
            processedValue = date.toISOString().slice(0, 19);
          } else {
            // タイムスタンプが無効な場合は現在値を維持
            processedValue = value;
          }
        } catch (e) {
          console.error('Invalid date format:', e);
          // エラー時は現在値を維持
          processedValue = value;
        }
      }
    }

    // メールアドレスの処理（バリデーションを削除）
    if (key === 'attendees' || key === 'to') {
      processedValue = value.trim();
    }

    // 入力値の更新
    setInputs(prev => ({
      ...prev,
      [key]: processedValue
    }));
  };

  const handleSave = () => {
    if (data.data.onUpdate) {
      console.log('Saving task inputs:', inputs);
      
      // 空の値を除外せずにそのまま送信
      const processedInputs = { ...inputs } as TaskInputs;
      
      // 日付フィールドの秒を00に設定
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
          <h4 className="font-medium">入力パラメータ</h4>
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
            <Button
              size="sm"
              variant="outline"
              onClick={handleSave}
              className="w-full"
            >
              <Save className="h-4 w-4 mr-2" />
              保存
            </Button>
          </div>
        </div>
        {task.outputs && Object.keys(task.outputs).length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium">出力ログ</h4>
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
            <Card className="relative w-[280px]">
              <CardHeader className="pb-2">
                <div className="flex justify-between items-center">
                  <h3 className="font-medium">{task.name}</h3>
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