import { pgTable, text, serial, jsonb, timestamp, boolean } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";

interface TaskIO {
  templateId?: string;
  template?: string;
  recipients?: string[];
  subject?: string;
  body?: string;
  attachments?: string[];
  apiKey?: string;
  credentials?: {
    clientId?: string;
    clientSecret?: string;
    refreshToken?: string;
  };
  result?: {
    success: boolean;
    message: string;
    data?: unknown;
  };
}

export const tasks = pgTable("tasks", {
  id: serial("id").primaryKey(),
  name: text("name").notNull().unique(),
  type: text("type").notNull(),
  inputs: jsonb("inputs").notNull().$type<TaskIO>(),
  outputs: jsonb("outputs").notNull().$type<TaskIO>(),
  status: text("status").notNull(),
  dependencies: jsonb("dependencies").notNull().$type<string[]>(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

interface WorkflowResult {
  success: boolean;
  message: string;
  taskResults: Record<string, TaskIO>;
}

export const workflows = pgTable("workflows", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  description: text("description"),
  tasks: jsonb("tasks").notNull().$type<string[]>(),
  status: text("status").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const workflowRuns = pgTable("workflow_runs", {
  id: serial("id").primaryKey(),
  workflowId: serial("workflow_id").references(() => workflows.id),
  status: text("status").notNull(),
  result: jsonb("result").$type<WorkflowResult>(),
  startedAt: timestamp("started_at").defaultNow().notNull(),
  completedAt: timestamp("completed_at"),
  error: text("error"),
});

interface DockerConfig {
  credentials: {
    clientId?: string;
    clientSecret?: string;
    refreshToken?: string;
    apiKey?: string;
  };
  env: Record<string, string>;
  ports?: string[];
  volumes?: string[];
  command?: string[];
}

export const dockerImages = pgTable("docker_images", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  tag: text("tag").notNull(),
  service: text("service").notNull(), // e.g., "gmail", "slack"
  config: jsonb("config").notNull().$type<DockerConfig>(),
  isBuilt: boolean("is_built").default(false).notNull(),
  buildError: text("build_error"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

// Zodスキーマの生成
export const insertTaskSchema = createInsertSchema(tasks);
export const selectTaskSchema = createSelectSchema(tasks);
export const insertWorkflowSchema = createInsertSchema(workflows);
export const selectWorkflowSchema = createSelectSchema(workflows);
export const insertWorkflowRunSchema = createInsertSchema(workflowRuns);
export const selectWorkflowRunSchema = createSelectSchema(workflowRuns);
export const insertDockerImageSchema = createInsertSchema(dockerImages);
export const selectDockerImageSchema = createSelectSchema(dockerImages);

// 型定義のエクスポート
export type InsertTask = typeof tasks.$inferInsert;
export type SelectTask = typeof tasks.$inferSelect;
export type InsertWorkflow = typeof workflows.$inferInsert;
export type SelectWorkflow = typeof workflows.$inferSelect;
export type InsertWorkflowRun = typeof workflowRuns.$inferInsert;
export type SelectWorkflowRun = typeof workflowRuns.$inferSelect;
export type InsertDockerImage = typeof dockerImages.$inferInsert;
export type SelectDockerImage = typeof dockerImages.$inferSelect;
