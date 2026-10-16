import { useId, useState } from "react";

function formatDate(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

// One row in the list. It switches between a read view, an edit form, and a
// "really delete?" confirmation.
export default function TaskItem({ task, busy, onChange, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [draftTitle, setDraftTitle] = useState(task.title);
  const [draftDescription, setDraftDescription] = useState(task.description ?? "");
  const [problem, setProblem] = useState("");
  const checkboxId = useId();
  const editTitleId = useId();
  const editDetailsId = useId();

  function startEditing() {
    setDraftTitle(task.title);
    setDraftDescription(task.description ?? "");
    setProblem("");
    setConfirmingDelete(false);
    setEditing(true);
  }

  async function saveEdit(event) {
    event.preventDefault();
    const cleanTitle = draftTitle.trim();
    if (!cleanTitle) {
      setProblem("The title can't be empty.");
      return;
    }
    const ok = await onChange(task, {
      title: cleanTitle,
      description: draftDescription.trim() || null,
    });
    if (ok) setEditing(false);
  }

  async function confirmDelete() {
    const ok = await onDelete(task);
    if (!ok) setConfirmingDelete(false);
  }

  if (editing) {
    return (
      <li className="task editing">
        <form className="edit-form" onSubmit={saveEdit} noValidate>
          <label className="visually-hidden" htmlFor={editTitleId}>
            Task title
          </label>
          <input
            id={editTitleId}
            className="field title-field"
            type="text"
            value={draftTitle}
            maxLength={200}
            onChange={(event) => setDraftTitle(event.target.value)}
            aria-invalid={problem ? "true" : undefined}
            autoFocus
          />
          <label className="visually-hidden" htmlFor={editDetailsId}>
            Details (optional)
          </label>
          <textarea
            id={editDetailsId}
            className="field"
            rows={2}
            value={draftDescription}
            maxLength={2000}
            placeholder="Details (optional)"
            onChange={(event) => setDraftDescription(event.target.value)}
          />
          <div className="form-footer">
            <p className="field-problem" role="alert">
              {problem}
            </p>
            <div className="actions">
              <button type="button" className="button" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button type="submit" className="button primary" disabled={busy}>
                {busy ? "Saving…" : "Save changes"}
              </button>
            </div>
          </div>
        </form>
      </li>
    );
  }

  const added = formatDate(task.created_at);

  return (
    <li className={`task${task.completed ? " done" : ""}`} aria-busy={busy}>
      <input
        id={checkboxId}
        className="check"
        type="checkbox"
        checked={task.completed}
        disabled={busy}
        onChange={() => onChange(task, { completed: !task.completed })}
      />
      <div className="task-body">
        <label className="task-title" htmlFor={checkboxId}>
          <span className="task-title-text">{task.title}</span>
        </label>
        {task.description && <p className="task-description">{task.description}</p>}
        {added && <p className="task-meta">Added {added}</p>}
      </div>

      <div className="actions">
        {confirmingDelete ? (
          <>
            <span className="confirm-text">Delete this task?</span>
            <button type="button" className="button" onClick={() => setConfirmingDelete(false)}>
              Keep task
            </button>
            <button type="button" className="button danger" disabled={busy} onClick={confirmDelete}>
              Delete task
            </button>
          </>
        ) : (
          <>
            <button type="button" className="button" disabled={busy} onClick={startEditing}>
              Edit
            </button>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => setConfirmingDelete(true)}
            >
              Delete
            </button>
          </>
        )}
      </div>
    </li>
  );
}
