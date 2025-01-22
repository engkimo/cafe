import { drizzle } from "drizzle-orm/neon-serverless";
import ws from "ws";
import * as schema from "@db/schema";

// Add debug logging for environment variables
console.log("Checking database configuration...");
if (!process.env.DATABASE_URL) {
  console.error("Missing DATABASE_URL environment variable");
  throw new Error(
    "DATABASE_URL must be set. Did you forget to provision a database?",
  );
}

console.log("Initializing database connection...");
let connection;

try {
  connection = process.env.DATABASE_URL;
  console.log("Database connection initialized successfully");
} catch (error) {
  console.error("Failed to initialize database connection:", error);
  throw error;
}

export const db = drizzle({
  connection,
  schema,
  ws: ws,
});