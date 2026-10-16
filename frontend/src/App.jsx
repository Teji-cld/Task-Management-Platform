import { useCallback, useEffect, useState } from "react";
import { createTask, deleteTask, listTasks, updateTask } from "./api.js";
import TaskForm from "./components/TaskForm.jsx";
import TaskItem from "./components/TaskItem.jsx";

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [status, setStatus] = useState("loading"); // "loading" | "ready" | "error"
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyIds, setBusyIds] = useState([]);

  const refresh = useCallback(async () => {
    setTasks(await listTasks());
  }, []);

  const loadInitial = useCallback(async () => {
    setStatus("loading");
    try {
      await refresh();
      setStatus("ready");
    } catch (err) {
      setLoadError(err.message);
      setStatus("error");
    }
  }, [refresh]);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  // Runs one change (create, update or delete), then reloads the list so the
  // screen always shows what the server really stores. Returns true on success.
  async function runAction(change, taskId = null) {
    setActionError("");
    if (taskId !== null) setBusyIds((ids) => [...ids, taskId]);
    try {
      await change();
      await refresh();
      return true;
    } catch (err) {
      setActionError(err.message);
      return false;
    } finally {
      if (taskId !== null) setBusyIds((ids) => ids.filter((id) => id !== taskId));
    }
  }

  const handleCreate = (task) => runAction(() => createTask(task));

  const handleChange = (task, changes) =>
    runAction(
      () =>
        updateTask(task.id, {
          title: task.title,
          description: task.description,
          completed: task.completed,
          ...changes,
        }),
      task.id
    );

  const handleDelete = (task) => runAction(() => deleteTask(task.id), task.id);

  const doneCount = tasks.filter((task) => task.completed).length;
  const openCount = tasks.length - doneCount;

  return (
    <main className="page">
      <header className="page-header">
        <h1>My Tasks</h1>
        {status === "ready" && tasks.length > 0 && (
          <p className="summary">
            {openCount} open, {doneCount} done
          </p>
        )}
      </header>

      <TaskForm onCreate={handleCreate} />

      {actionError && (
        <div className="banner" role="alert">
          <span>{actionError}</span>
          <button type="button" className="link-button" onClick={() => setActionError("")}>
            Dismiss
          </button>
        </div>
      )}

      {status === "loading" && (
        <p className="state-message" role="status">
          Loading tasks…
        </p>
      )}

      {status === "error" && (
        <div className="state-message error-state" role="alert">
          <p>Couldn't load your tasks. {loadError}</p>
          <button type="button" className="button" onClick={loadInitial}>
            Try again
          </button>
        </div>
      )}

      {status === "ready" && tasks.length === 0 && (
        <p className="state-message">No tasks yet. Add your first one above.</p>
      )}

      {status === "ready" && tasks.length > 0 && (
        <ul className="task-list">
          {tasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              busy={busyIds.includes(task.id)}
              onChange={handleChange}
              onDelete={handleDelete}
            />
          ))}
        </ul>
      )}
    </main>
  );
}
