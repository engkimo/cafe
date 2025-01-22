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
    pending: 'Pending',
    running: 'Running',
    completed: 'Completed',
    failed: 'Failed'
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

  // Calculate default times for 30 minutes and 1 hour from current time
  const getDefaultTimes = () => {
    const now = new Date();
    const startTime = new Date(now.getTime() + 30 * 60000); // 30分後
    const endTime = new Date(now.getTime() + 60 * 60000);   // 1時間後
    
    // Convert to YYYY-MM-DDThh:mm:ss format (set seconds to 00)
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

  // Define default input fields based on task type
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
    // Use existing task input values if available
    return {
      ...defaults,
      ...Object.fromEntries(
        Object.entries(task.inputs).filter(([_, value]) => value !== '')
      )
    };
  });

  const handleInputChange = (key: string, value: string) => {
    let processedValue = value;

    // Process datetime input (more flexibly)
    if (key.includes('time')) {
      if (value === '') {
        // If value is empty, set default datetime
        const { start_time, end_time } = getDefaultTimes();
        processedValue = key === 'start_time' ? start_time : end_time;
      } else {
        try {
          // Convert input datetime to YYYY-MM-DDThh:mm:ss format
          const date = new Date(value);
          const timestamp = date.getTime();
          if (!Number.isNaN(timestamp)) {
            // Set seconds to 00
            date.setSeconds(0);
            processedValue = date.toISOString().slice(0, 19);
          } else {
            // If timestamp is invalid, keep current value
            processedValue = value;
          }
        } catch (e) {
          console.error('Invalid date format:', e);
          // On error, keep current value
          processedValue = value;
        }
      }
    }

    // Process email addresses (validation removed)
    if (key === 'attendees' || key === 'to') {
      processedValue = value.trim();
    }

    // Update input value
    setInputs(prev => ({
      ...prev,
      [key]: processedValue
    }));
  };

  const handleSave = () => {
    if (data.data.onUpdate) {
      console.log('Saving task inputs:', inputs);
      
      // Send all values without excluding empty ones
      const processedInputs = { ...inputs } as TaskInputs;
      
      // Set seconds to 00 for date fields
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
          <h4 className="font-medium">Input Parameters</h4>
          <div className="space-y-4">
            <div className="space-y-2">
              {Object.entries(inputs).map(([key, value]) => {
                const inputId = `task-${task.id}-input-${key}`;
                const inputType = key.includes('time') ? 'datetime-local' : 'text';
                const placeholder = {
                  attendees: 'Enter email addresses (comma separated)',
                  subject: 'Enter subject',
                  body: 'Enter message body',
                  to: 'Enter recipient email',
                  start_time: 'Start time',
                  end_time: 'End time'
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
              Save
            </Button>
          </div>
        </div>
        {task.outputs && Object.keys(task.outputs).length > 0 && (
          <div className="space-y-2">
            <h4 className="font-medium">Output Log</h4>
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
                  <div>Type: {task.type}</div>
                  {task.dependencies.length > 0 && (
                    <div>Dependencies: {task.dependencies.join(', ')}</div>
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