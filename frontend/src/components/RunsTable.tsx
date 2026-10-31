import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { type Run, type Persona, date, displayRunStatus, isRunActive } from "../api";

interface RunsTableProps {
  runs: Run[];
  personas: Persona[];
}

type StatusFilter = "all" | "active" | "completed" | "failed";

export default function RunsTable({ runs, personas }: RunsTableProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  const filteredRuns = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return runs.filter((run) => {
      const personaName = personas.find((p) => p.id === run.persona_id)?.name || run.persona_id;
      const matchesQuery = !needle || [
        run.apk_name,
        run.id,
        run.apk_sha256,
        personaName,
        run.status
      ].some((value) => value?.toLocaleLowerCase().includes(needle));
      const matchesStatus =
        status === "all" ||
        (status === "active" && isRunActive(run.status)) ||
        (status === "completed" && run.status === "completed") ||
        (status === "failed" && (run.status === "failed" || run.status === "timed_out"));
      return matchesQuery && matchesStatus;
    });
  }, [runs, personas, query, status]);

  return (
    <div className="runs-browser">
      <div className="runs-toolbar">
        <label className="runs-search">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search test runs</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search APK, run ID, persona or hash…"
          />
          {query && (
            <button type="button" className="runs-clear" onClick={() => setQuery("")} aria-label="Clear search">
              <X size={14} />
            </button>
          )}
        </label>
        <label className="runs-filter">
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)} aria-label="Filter runs by status">
            <option value="all">All statuses</option>
            <option value="active">In progress</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed / timed out</option>
          </select>
        </label>
        <p className="runs-count" role="status" aria-live="polite">
          Showing <b>{filteredRuns.length}</b> of <b>{runs.length}</b> runs
        </p>
      </div>

      {filteredRuns.length === 0 ? (
        <div className="empty-state runs-empty">
          <div className="empty-icon"><Search size={21} /></div>
          <b>No matching test runs</b>
          <p>Try a different search term or status filter.</p>
          <button type="button" className="secondary-button" onClick={() => { setQuery(""); setStatus("all"); }}>
            Clear filters
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>APPLICATION / RUN</th>
                <th>PERSONA</th>
                <th>CREATED</th>
                <th>STATUS</th>
                <th>APK SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => {
                const personaName = personas.find((p) => p.id === run.persona_id)?.name || run.persona_id;
                const statusClass =
                  run.status === "completed"
                    ? "done"
                    : run.status === "failed" || run.status === "timed_out"
                    ? "failed"
                    : "pending";

                return (
                  <tr key={run.id}>
                    <td>
                      <button
                        className="text-button run-link"
                        onClick={() => navigate(`/runs/${encodeURIComponent(run.id)}`)}
                      >
                        <b>{run.apk_name || "APK not attached"}</b>
                        <small className="table-sub">{run.id}</small>
                      </button>
                    </td>
                    <td>{personaName}</td>
                    <td>{date(run.created_at)}</td>
                    <td>
                      <span className={"run-status " + statusClass}>
                        {displayRunStatus(run.status)}
                      </span>
                    </td>
                    <td><code title={run.apk_sha256 || undefined}>{run.apk_sha256?.slice(0, 16) || "—"}</code></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
