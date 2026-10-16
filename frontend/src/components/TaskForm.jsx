import { useId, useState } from "react";

// The "add a task" form at the top of the page.
export default function TaskForm({ onCreate }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState("");
  const titleId = useId();
  const detailsId = useId();

  async function handleSubmit(event) {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setProblem("Enter a title for the task.");
      return;
    }
    setProblem("");
    setSubmitting(true);
    const ok = await onCreate({
      title: cleanTitle,
      description: description.trim() || null,
      completed: false,
    });
    setSubmitting(false);
    if (ok) {
      setTitle("");
      setDescription("");
    }
  }

  return (
    <form className="add-form" onSubmit={handleSubmit} noValidate>
      <label className="visually-hidden" htmlFor={titleId}>
        Task title
      </label>
      <input
        id={titleId}
        className="field title-field"
        type="text"
        value={title}
        maxLength={200}
        placeholder="What needs doing?"
        onChange={(event) => setTitle(event.target.value)}
        aria-invalid={problem ? "true" : undefined}
        aria-describedby={problem ? `${titleId}-problem` : undefined}
      />
      <label className="visually-hidden" htmlFor={detailsId}>
        Details (optional)
      </label>
      <textarea
        id={detailsId}
        className="field"
        rows={2}
        value={description}
        maxLength={2000}
        placeholder="Details (optional)"
        onChange={(event) => setDescription(event.target.value)}
      />
      <div className="form-footer">
        <p className="field-problem" id={`${titleId}-problem`} role="alert">
          {problem}
        </p>
        <button className="button primary" type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add task"}
        </button>
      </div>
    </form>
  );
}
