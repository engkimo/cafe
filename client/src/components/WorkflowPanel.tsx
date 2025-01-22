import type { Task } from "@/pages/Home";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { PlayCircle, PauseCircle, RotateCcw, Trash2 } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import type { Node, Edge, NodeTypes } from '@xyflow/react';
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState, Position, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import TaskNode, { type TaskNodeData } from './TaskNode';

interface WorkflowPanelProps {
  tasks: Task[];
  ws: WebSocket | null;
}

type FlowNode = Node<{ data: TaskNodeData }>;
type FlowEdge = Edge;

interface TaskInputs {
  attendees?: string;
  subject?: string;
  body?: string;
  to?: string;
  start_time?: string;
  end_time?: string;
  [key: string]: string | undefined;
}

const nodeTypes: NodeTypes = {
  taskNode: TaskNode,
};

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const NODE_WIDTH = 280;
const NODE_HEIGHT = 120;

const createNode = (
  task: Task,
  position: { x: number; y: number },
  handleExecuteTask: (taskId: string) => void,
  handleUpdateTask: (taskId: string, inputs: TaskInputs) => void,
  isExecuting: boolean
): FlowNode => ({
  id: task.id.toString(),
  type: 'taskNode',
  position,
  data: {
    data: {
      task,
      onExecute: handleExecuteTask,
      onUpdate: handleUpdateTask,
      isExecuting
    }
  },
  sourcePosition: Position.Bottom,
  targetPosition: Position.Top,
});

const createEdge = (source: string, target: string): FlowEdge => ({
  id: `${source}-${target}`,
  source,
  target,
  type: 'smoothstep',
  animated: true,
  style: { stroke: 'hsl(var(--primary))' },
  markerEnd: {
    type: MarkerType.ArrowClosed,
  },
});

const getLayoutedElements = (
  tasks: Task[],
  handleExecuteTask: (taskId: string) => void,
  handleUpdateTask: (taskId: string, inputs: TaskInputs) => void,
  isExecuting: boolean,
  direction = 'TB'
) => {
  const nodes: FlowNode[] = [];
  const edges: FlowEdge[] = [];

  if (tasks.length === 0) {
    return { nodes: [], edges: [] };
  }

  dagreGraph.setGraph({ rankdir: direction });

  for (const task of tasks) {
    dagreGraph.setNode(task.id.toString(), { width: NODE_WIDTH, height: NODE_HEIGHT });
  }

  for (const task of tasks) {
    if (task.dependencies) {
      for (const depName of task.dependencies) {
        const depTask = tasks.find((t) => t.name === depName);
        if (depTask) {
          dagreGraph.setEdge(depTask.id.toString(), task.id.toString());
          edges.push(createEdge(depTask.id.toString(), task.id.toString()));
        }
      }
    }
  }

  dagre.layout(dagreGraph);

  for (const task of tasks) {
    const nodeWithPosition = dagreGraph.node(task.id.toString());
    nodes.push(
      createNode(
        task,
        {
          x: nodeWithPosition.x - NODE_WIDTH / 2,
          y: nodeWithPosition.y - NODE_HEIGHT / 2,
        },
        handleExecuteTask,
        handleUpdateTask,
        isExecuting
      )
    );
  }

  return { nodes, edges };
};

export default function WorkflowPanel({ tasks, ws }: WorkflowPanelProps) {
  const { toast } = useToast();
  const [isExecuting, setIsExecuting] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);

  const handleExecuteTask = useCallback((taskId: string) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast({
        title: "Error",
        description: "WebSocket connection is not established",
        variant: "destructive",
      });
      return;
    }

    console.log('Executing task:', taskId);
    ws.send(JSON.stringify({
      type: "execute_task",
      taskId
    }));
  }, [ws, toast]);

  const handleUpdateTask = useCallback((taskId: string, inputs: TaskInputs) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast({
        title: "Error",
        description: "WebSocket connection is not established",
        variant: "destructive",
      });
      return;
    }

    console.log('Updating task:', taskId, 'with inputs:', inputs);
    ws.send(JSON.stringify({
      type: "update_task",
      taskId,
      inputs
    }));
  }, [ws, toast]);

  useEffect(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      tasks,
      handleExecuteTask,
      handleUpdateTask,
      isExecuting,
      'TB'
    );
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [tasks, handleExecuteTask, handleUpdateTask, isExecuting, setNodes, setEdges]);

  const handleDeleteAllTasks = useCallback(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast({
        title: "Error",
        description: "WebSocket connection is not established",
        variant: "destructive",
      });
      return;
    }

    ws.send(JSON.stringify({
      type: "delete_all_tasks"
    }));
  }, [ws, toast]);

  const handleExecuteAll = useCallback(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast({
        title: "Error",
        description: "WebSocket connection is not established",
        variant: "destructive",
      });
      return;
    }

    const pendingTasks = tasks.filter(task => task.status === 'pending');
    if (pendingTasks.length === 0) {
      toast({
        title: "Notice",
        description: "No executable tasks available",
      });
      return;
    }

    setIsExecuting(true);
    ws.send(JSON.stringify({
      type: "execute_all_tasks",
      taskIds: nodes.map(node => node.id)
    }));
  }, [ws, toast, tasks, nodes]);

  const handleRestartAll = useCallback(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      for (const task of tasks) {
        ws.send(JSON.stringify({
          type: "reset_task",
          taskId: task.id
        }));
      }
    }
  }, [ws, tasks]);

  const renderExecuteButton = () => {
    if (tasks.length === 0) return null;

    const buttonBaseClass = "flex items-center justify-center w-12 h-12 rounded-full bg-beige hover:bg-beige/90 text-foreground transition-all duration-200";

    if (tasks.every(task => task.status === 'completed' || task.status === 'failed')) {
      return (
        <Button size="lg" onClick={handleRestartAll} className={buttonBaseClass}>
          <RotateCcw className="h-6 w-6" />
        </Button>
      );
    }

    if (isExecuting) {
      return (
        <Button size="lg" onClick={() => setIsExecuting(false)} className={buttonBaseClass}>
          <PauseCircle className="h-6 w-6" />
        </Button>
      );
    }

    if (tasks.every(task => task.status === 'pending')) {
      return (
        <Button size="lg" onClick={handleExecuteAll} className={buttonBaseClass}>
          <PlayCircle className="h-6 w-6" />
        </Button>
      );
    }

    return null;
  };

  return (
    <Card className="h-full rounded-none border-r flex flex-col">
      <div className="p-4 border-b">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold">Workflow</h2>
          {renderExecuteButton()}
        </div>
      </div>
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
      {tasks.length > 0 && (
        <div className="p-4 border-t">
          <Button
            size="sm"
            variant="ghost"
            onClick={handleDeleteAllTasks}
            className="w-full flex items-center justify-center gap-2 bg-beige hover:bg-beige/90 text-foreground"
          >
            <Trash2 className="h-4 w-4" />
            Delete All Tasks
          </Button>
        </div>
      )}
    </Card>
  );
}